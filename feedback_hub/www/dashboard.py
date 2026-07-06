import frappe
import frappe.sessions

from feedback_hub.utils import display_roles

no_cache = 1


def get_context(context):
	# Task 6.5: Guest (including a session that has expired, which resolves
	# back to Guest) is redirected to Login rather than shown an error.
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	user = frappe.get_cached_doc("User", frappe.session.user)
	context.no_header = True
	context.title = "Dashboard"
	context.first_name = user.first_name
	context.roles = display_roles(frappe.session.user)
	# The shared navbar (org-management module) now renders an org-switcher
	# here, which can POST to switch_organization - needs a CSRF token.
	context.csrf_token = frappe.sessions.get_csrf_token()
