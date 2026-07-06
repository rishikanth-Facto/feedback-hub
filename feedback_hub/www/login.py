import frappe

no_cache = 1


def get_context(context):
	# Task 6.7 / spec "Authenticated Users Are Redirected Away From Login/Signup":
	# re-authenticating is not a valid action for an already-logged-in user.
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/dashboard"
		raise frappe.Redirect

	context.no_header = True
	context.title = "Log In"
