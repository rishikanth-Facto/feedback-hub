import frappe
from frappe import _

from feedback_hub.organization import context
from feedback_hub.organization.permissions import get_active_membership
from feedback_hub.product.permissions import PRODUCT_ROLES
from feedback_hub.product.utils import BOARD_VISIBILITIES, PRODUCT_STATUSES

PRODUCT_FIELDS = [
	"name",
	"product_name",
	"slug",
	"description",
	"status",
	"organization",
	"product_owner",
	"owner",
	"creation",
	"modified",
]

BOARD_FIELDS = ["name", "board_name", "slug", "description", "visibility", "product", "owner", "creation", "modified"]


def _require_active_organization():
	organization = context.get_active_organization()
	if not organization:
		frappe.throw(_("No active organization selected. Switch to an organization first."), frappe.ValidationError)
	return organization


def _require_product_management(organization, user=None):
	user = user or frappe.session.user
	membership = get_active_membership(user, organization)
	if not membership or membership.role not in PRODUCT_ROLES:
		frappe.throw(
			_("You must be an Organization Admin or Product Owner of this organization to perform this action."),
			frappe.PermissionError,
		)


def _get_product_in_active_organization(product):
	organization = _require_active_organization()
	doc = frappe.get_doc("Product", product)
	if doc.organization != organization:
		# Cross-organization access is never revealed as "exists but denied" -
		# same not-found shape as a missing id (spec: product-board-permissions
		# "Cross-Organization Access Is Prevented").
		frappe.throw(_("Product not found."), frappe.DoesNotExistError)
	return doc


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------


def create_product(product_name, description=None):
	organization = _require_active_organization()
	_require_product_management(organization)

	if not product_name or not product_name.strip():
		frappe.throw(_("Product Name is required."), frappe.ValidationError)

	doc = frappe.get_doc(
		{
			"doctype": "Product",
			"product_name": product_name.strip(),
			"description": description,
			"organization": organization,
		}
	)
	doc.insert()
	return doc.as_dict()


def get_product(product):
	doc = _get_product_in_active_organization(product)
	frappe.has_permission("Product", "read", doc, throw=True)
	return {field: doc.get(field) for field in PRODUCT_FIELDS}


def list_products():
	organization = _require_active_organization()
	membership = get_active_membership(frappe.session.user, organization)
	if not membership or membership.role not in PRODUCT_ROLES:
		return []

	return frappe.get_list(
		"Product", filters={"organization": organization}, fields=PRODUCT_FIELDS, order_by="modified desc"
	)


def update_product(product, product_name=None, description=None, status=None):
	organization = _require_active_organization()
	_require_product_management(organization)
	doc = _get_product_in_active_organization(product)

	if product_name:
		doc.product_name = product_name.strip()
	if description is not None:
		doc.description = description
	if status:
		if status not in PRODUCT_STATUSES:
			frappe.throw(_("Invalid status."), frappe.ValidationError)
		doc.status = status
	doc.save()
	return doc.as_dict()


def delete_product(product, force=False):
	organization = _require_active_organization()
	_require_product_management(organization)
	doc = _get_product_in_active_organization(product)

	if not force:
		boards = frappe.db.count("Board", {"product": doc.name})
		if boards:
			frappe.throw(
				_(
					"Cannot delete product: {0} board(s) still exist. "
					"Remove them first or pass force=true to force delete."
				).format(boards),
				frappe.LinkExistsError,
			)
		frappe.delete_doc("Product", doc.name, ignore_permissions=True)
		return {"product": doc.name, "deleted": True}

	frappe.flags.force_delete_product = True
	try:
		frappe.delete_doc("Product", doc.name, ignore_permissions=True)
	finally:
		frappe.flags.force_delete_product = False
	return {"product": doc.name, "deleted": True}


# ---------------------------------------------------------------------------
# Board CRUD
# ---------------------------------------------------------------------------


def _get_board_in_active_organization(board):
	organization = _require_active_organization()
	doc = frappe.get_doc("Board", board)
	product_org = frappe.db.get_value("Product", doc.product, "organization")
	if product_org != organization:
		frappe.throw(_("Board not found."), frappe.DoesNotExistError)
	return doc


def create_board(product, board_name, visibility, description=None):
	product_doc = _get_product_in_active_organization(product)
	_require_product_management(product_doc.organization)

	if not board_name or not board_name.strip():
		frappe.throw(_("Board Name is required."), frappe.ValidationError)
	if not visibility:
		frappe.throw(_("Visibility is required."), frappe.ValidationError)
	if visibility not in BOARD_VISIBILITIES:
		frappe.throw(_("Invalid visibility."), frappe.ValidationError)
	if product_doc.status == "Archived":
		# Create-time gate only - editing a board that was validly created
		# before its product was archived is not blocked (design.md Decision 10).
		frappe.throw(_("Cannot create a board under an archived product."), frappe.ValidationError)

	doc = frappe.get_doc(
		{
			"doctype": "Board",
			"board_name": board_name.strip(),
			"visibility": visibility,
			"description": description,
			"product": product_doc.name,
		}
	)
	doc.insert()
	return doc.as_dict()


def get_board(board):
	doc = _get_board_in_active_organization(board)
	frappe.has_permission("Board", "read", doc, throw=True)
	return {field: doc.get(field) for field in BOARD_FIELDS}


def list_boards(product=None):
	organization = _require_active_organization()
	membership = get_active_membership(frappe.session.user, organization)
	if not membership:
		return []

	filters = {}
	if product:
		product_doc = _get_product_in_active_organization(product)
		filters["product"] = product_doc.name
	else:
		filters["product"] = ["in", frappe.get_all("Product", filters={"organization": organization}, pluck="name")]

	if membership.role == "Customer":
		filters["visibility"] = "Public"

	return frappe.get_list("Board", filters=filters, fields=BOARD_FIELDS, order_by="modified desc")


def list_visible_products():
	"""Products that have at least one Board visible to the caller in the
	active organization - unlike list_products (Organization Admin/Product
	Owner only), this works for every role, including Customer/Moderator/
	Developer, who have no access to the Product doctype itself. Needed so
	the Feedback module's product-grouped Kanban view (feedback_list.html)
	can offer a product picker without granting any new Product permission -
	reuses the same Board-visibility rule as list_boards rather than
	introducing a second one."""
	organization = _require_active_organization()
	membership = get_active_membership(frappe.session.user, organization)
	if not membership:
		return []

	board_filters = {"product": ["in", frappe.get_all("Product", filters={"organization": organization}, pluck="name")]}
	if membership.role == "Customer":
		board_filters["visibility"] = "Public"

	product_names = sorted(set(frappe.get_list("Board", filters=board_filters, pluck="product")))
	if not product_names:
		return []
	return frappe.get_all(
		"Product", filters={"name": ["in", product_names]}, fields=["name", "product_name"], order_by="product_name asc"
	)


def update_board(board, board_name=None, visibility=None, description=None):
	doc = _get_board_in_active_organization(board)
	frappe.has_permission("Board", "write", doc, throw=True)

	if board_name:
		doc.board_name = board_name.strip()
	if description is not None:
		doc.description = description
	if visibility:
		if visibility not in BOARD_VISIBILITIES:
			frappe.throw(_("Invalid visibility."), frappe.ValidationError)
		doc.visibility = visibility
	doc.save(ignore_permissions=True)
	return doc.as_dict()


def delete_board(board):
	doc = _get_board_in_active_organization(board)
	frappe.has_permission("Board", "delete", doc, throw=True)
	frappe.delete_doc("Board", doc.name, ignore_permissions=True)
	return {"board": doc.name, "deleted": True}
