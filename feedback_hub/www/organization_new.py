import frappe
import frappe.sessions

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_header = True
	context.title = "New Organization"
	context.csrf_token = frappe.sessions.get_csrf_token()
