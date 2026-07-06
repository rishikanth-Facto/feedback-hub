import frappe


def record_activity(feedback_name, text):
	"""Reuses Frappe's own native per-document Comment/Info timeline (visible
	in Desk's "Activity" tab for any document) instead of a bespoke Activity
	log - Module 5 design.md Decision 10, same "reuse framework infrastructure"
	precedent as Module 4's Version-log-based Activity History."""
	frappe.get_doc("Feedback", feedback_name).add_comment(comment_type="Info", text=text)
