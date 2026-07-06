import frappe
import frappe.sessions

from feedback_hub.feedback.permissions import can_edit_or_delete_feedback
from feedback_hub.feedback.service import get_feedback

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	feedback = frappe.form_dict.get("id")
	if not feedback or not frappe.db.exists("Feedback", feedback):
		frappe.local.flags.redirect_location = "/feedback_list"
		raise frappe.Redirect

	doc = frappe.get_doc("Feedback", feedback)
	if not can_edit_or_delete_feedback(doc, "write"):
		# Not reachable without update permission - same guard shape as
		# product_new.py/board_new.py for callers who lack management rights.
		frappe.local.flags.redirect_location = "/feedback_detail?id=" + feedback
		raise frappe.Redirect

	context.no_header = True
	context.title = "Edit Feedback"
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.feedback = get_feedback(feedback)
