import frappe

no_cache = 1


def get_context(context):
	context.no_header = True
	context.title = "Feedback Hub"
	context.is_guest = frappe.session.user == "Guest"
