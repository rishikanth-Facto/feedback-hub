import frappe

from feedback_hub.organization.context import get_active_organization
from feedback_hub.organization.permissions import get_active_membership

# Reuses feedback_hub.organization.permissions.get_active_membership and
# feedback_hub.organization.context.get_active_organization directly rather
# than re-deriving membership lookups (design.md Decision 2).

PRODUCT_ROLES = ("Organization Admin", "Product Owner")
BOARD_FULL_ROLES = ("Organization Admin", "Product Owner")


def resolve_role_in_active_organization(user, organization):
	"""Return the caller's Active-membership role in `organization`, but only
	when `organization` is also the caller's currently active Organization
	(design.md Decision 3) - a qualifying role in an organization that isn't
	active right now grants nothing. Also used by www pages (board_detail.py)
	to decide which controls to render, not just by the permission hooks."""
	if not organization or organization != get_active_organization():
		return None
	membership = get_active_membership(user, organization)
	return membership.role if membership else None


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------


def has_permission_product(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	role = resolve_role_in_active_organization(user, doc.organization)
	# Only Organization Admin/Product Owner have any access to Products at
	# all - every ptype, including read (design.md Decision 11); Moderator/
	# Developer/Customer are simply not in Product's world.
	return role in PRODUCT_ROLES


def get_permission_query_conditions_product(user=None):
	user = user or frappe.session.user
	organization = get_active_organization()
	if not organization:
		return "1=0"
	membership = get_active_membership(user, organization)
	if not membership or membership.role not in PRODUCT_ROLES:
		return "1=0"
	return f"`tabProduct`.organization = {frappe.db.escape(organization)}"


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------


def has_permission_board(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	ptype = ptype or "read"
	organization = frappe.db.get_value("Product", doc.product, "organization") if doc.product else None
	role = resolve_role_in_active_organization(user, organization)
	if not role:
		return False
	if role in BOARD_FULL_ROLES:
		return True
	if role == "Moderator":
		return ptype in ("read", "write")
	if role == "Developer":
		return ptype == "read"
	if role == "Customer":
		return ptype == "read" and doc.visibility == "Public"
	return False


def get_permission_query_conditions_board(user=None):
	user = user or frappe.session.user
	organization = get_active_organization()
	if not organization:
		return "1=0"
	membership = get_active_membership(user, organization)
	if not membership:
		return "1=0"

	condition = (
		"`tabBoard`.product in (select `name` from `tabProduct` where `organization` = {organization})"
	).format(organization=frappe.db.escape(organization))
	if membership.role == "Customer":
		# Enforced in the query condition, not only has_permission, so a
		# Customer's board listing never leaks Private/Internal row existence
		# (design.md Decision 12).
		condition += " and `tabBoard`.visibility = 'Public'"
	return condition
