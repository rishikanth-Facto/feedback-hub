import frappe
import frappe.sessions

from feedback_hub.feedback.permissions import STATUS_MOVE_ROLES
from feedback_hub.organization import context as org_context
from feedback_hub.organization.permissions import get_active_membership
from feedback_hub.product.permissions import resolve_role_in_active_organization

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_header = True
	context.title = "Feedback"
	context.csrf_token = frappe.sessions.get_csrf_token()

	organization = org_context.get_active_organization()
	membership = get_active_membership(frappe.session.user, organization) if organization else None
	# Anyone with an active membership can attempt to create feedback - the
	# create form's own board picker only ever lists boards they can
	# actually read, the real gate (feedback-lifecycle: create is board-read
	# gated, unchanged from the pre-existing Kanban create flow).
	context.can_create = bool(membership)
	# Cosmetic-only "is dragging worth offering" hint, same STATUS_MOVE_ROLES
	# check board_detail.py's can_move_status_role uses - Moderator now also
	# gets a slice of the lifecycle (design.md Decision 14), not just
	# Organization Admin/Product Owner. The real, transition-aware gate is
	# service.move_status's can_move_status(doc, new_status).
	role = resolve_role_in_active_organization(frappe.session.user, organization) if organization else None
	context.can_move_feedback = role in STATUS_MOVE_ROLES
