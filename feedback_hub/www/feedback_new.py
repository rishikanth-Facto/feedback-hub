import frappe
import frappe.sessions

from feedback_hub.organization import context as org_context
from feedback_hub.organization.permissions import get_active_membership

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	organization = org_context.get_active_organization()
	membership = get_active_membership(frappe.session.user, organization) if organization else None
	if not membership:
		frappe.local.flags.redirect_location = "/feedback_list"
		raise frappe.Redirect

	context.no_header = True
	context.title = "New Feedback"
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.preselected_board = frappe.form_dict.get("board") or ""
