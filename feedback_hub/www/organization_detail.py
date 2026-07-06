import frappe
import frappe.sessions

from feedback_hub.organization.permissions import get_active_membership

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_header = True
	context.csrf_token = frappe.sessions.get_csrf_token()

	organization = frappe.form_dict.get("id")
	if not organization or not frappe.db.exists("Organization", organization):
		context.title = "Organization Not Found"
		context.not_found = True
		return

	# Non-members get the same not-found state as a missing id - the detail
	# page never reveals that an organization exists to a non-member (spec:
	# organization-permissions "Non-Members Denied Access").
	membership = get_active_membership(frappe.session.user, organization)
	if not membership:
		context.title = "Organization Not Found"
		context.not_found = True
		return

	org = frappe.get_doc("Organization", organization)
	context.title = org.organization_name
	context.organization = org
	context.is_admin = membership.role == "Organization Admin"
