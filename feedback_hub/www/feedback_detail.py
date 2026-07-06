import frappe
import frappe.sessions

from feedback_hub.feedback.permissions import can_edit_or_delete_feedback
from feedback_hub.feedback.service import get_feedback

no_cache = 1

# Mirrors public/js/fh_ui.js's FH_STATUS_BADGE_CLASS map for this one
# server-rendered status badge - kept here rather than a shared Jinja filter
# since it's the only server-side consumer of the status->badge-class mapping.
FH_STATUS_BADGE_CLASSES = {
	"New": "fh-badge-new",
	"Under Review": "fh-badge-under-review",
	"Approved": "fh-badge-approved",
	"Rejected": "fh-badge-rejected",
	"Planned": "fh-badge-planned",
	"In Progress": "fh-badge-in-progress",
	"Released": "fh-badge-released",
	"Closed": "fh-badge-closed",
}


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	context.no_header = True
	context.csrf_token = frappe.sessions.get_csrf_token()

	feedback = frappe.form_dict.get("id")
	if not feedback or not frappe.db.exists("Feedback", feedback):
		context.title = "Feedback Not Found"
		context.not_found = True
		return

	doc = frappe.get_doc("Feedback", feedback)
	if not frappe.has_permission("Feedback", "read", doc):
		# Never reveal existence to a caller without read access - same
		# not-found shape as product_detail.py/board_detail.py (spec:
		# feedback-permissions "Cross-Organization Access Is Prevented").
		context.title = "Feedback Not Found"
		context.not_found = True
		return

	context.title = doc.title
	context.feedback = get_feedback(feedback)
	context.can_update = can_edit_or_delete_feedback(doc, "write")
	context.can_delete = can_edit_or_delete_feedback(doc, "delete")
	context.FH_STATUS_BADGE_CLASSES = FH_STATUS_BADGE_CLASSES
