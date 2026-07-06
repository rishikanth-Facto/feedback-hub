import frappe
import frappe.sessions

from feedback_hub.utils import display_roles

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	# Note: context.user is reserved by Frappe's own website rendering
	# pipeline (frappe/website/page_renderers/template_page.py sets
	# context["user"] = <session user string> after get_context() returns,
	# clobbering anything we put there) - use a different key for the doc.
	context.no_header = True
	context.title = "Profile"
	context.profile_user = frappe.get_cached_doc("User", frappe.session.user)
	context.roles = display_roles(frappe.session.user)
	context.csrf_token = frappe.sessions.get_csrf_token()
