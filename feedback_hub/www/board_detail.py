import frappe
import frappe.sessions

from feedback_hub.feedback.permissions import can_move_status_role
from feedback_hub.organization import context as org_context
from feedback_hub.product.permissions import BOARD_FULL_ROLES, PRODUCT_ROLES, resolve_role_in_active_organization

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_header = True
	context.csrf_token = frappe.sessions.get_csrf_token()

	board = frappe.form_dict.get("id")
	organization = org_context.get_active_organization()

	if not board or not frappe.db.exists("Board", board):
		context.title = "Board Not Found"
		context.not_found = True
		return

	doc = frappe.get_doc("Board", board)
	product_org = frappe.db.get_value("Product", doc.product, "organization")
	role = resolve_role_in_active_organization(frappe.session.user, organization) if product_org == organization else None

	can_read = bool(role) and (role != "Customer" or doc.visibility == "Public")
	if not can_read:
		# Never reveal existence to a caller without read access - same
		# not-found shape as product_detail.py (spec: product-board-
		# permissions "Cross-Organization Access Is Prevented").
		context.title = "Board Not Found"
		context.not_found = True
		return

	context.title = doc.board_name
	context.board = doc
	context.can_update = role in BOARD_FULL_ROLES or role == "Moderator"
	context.can_delete = role in BOARD_FULL_ROLES
	# Product Detail is itself invisible to non-manager roles (spec:
	# product-board-permissions) - only link back to it when the caller
	# could actually open it.
	context.can_view_product = role in PRODUCT_ROLES
	# Cosmetic only - decides whether Kanban cards render as draggable at all
	# (Organization Admin/Moderator/Product Owner, each with their own half of
	# the split moderation/roadmap lifecycle, design.md Decision 14). The real,
	# transition-aware gate is service.move_status's can_move_status(doc,
	# new_status), which always re-validates server-side regardless of what
	# the client attempted to drag.
	context.can_move_status = can_move_status_role(doc.name)
