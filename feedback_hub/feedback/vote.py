import frappe
from frappe import _

from feedback_hub.feedback.events import emit_event
from feedback_hub.feedback.permissions import _require_not_archived, require_board_read
from feedback_hub.feedback.timeline import record_activity
from feedback_hub.organization.api import handle_errors
from feedback_hub.utils import api_response, require_login


def _toggle_vote(feedback):
	"""Core toggle logic (Module 5 design.md Decision 3): one Feedback Vote
	row per (feedback, user) forever, is_deleted flipped in place rather than
	inserted/hard-deleted, so the unique vote_key constraint holds across the
	full toggle history."""
	doc = frappe.get_doc("Feedback", feedback)  # raises DoesNotExistError for a deleted item
	_require_not_archived(doc)
	require_board_read(doc.board)

	existing = frappe.db.get_value(
		"Feedback Vote", {"feedback": feedback, "user": frappe.session.user}, ["name", "is_deleted"], as_dict=True
	)
	if existing:
		vote_doc = frappe.get_doc("Feedback Vote", existing.name)
		vote_doc.is_deleted = 0 if vote_doc.is_deleted else 1
		vote_doc.save(ignore_permissions=True)
		voted = not vote_doc.is_deleted
	else:
		frappe.get_doc({"doctype": "Feedback Vote", "feedback": feedback, "user": frappe.session.user, "is_deleted": 0}).insert()
		voted = True

	total_votes = frappe.db.get_value("Feedback", feedback, "vote_count")
	record_activity(feedback, "Vote Added" if voted else "Vote Removed")
	emit_event("vote", doc, voted=voted)
	return {"feedback": feedback, "voted": voted, "total_votes": total_votes}


@frappe.whitelist(methods=["POST"])
@handle_errors
def toggle_vote(feedback_id=None):
	require_login()
	data = _toggle_vote(feedback_id)
	message = _("Vote recorded.") if data.get("voted") else _("Vote removed.")
	return api_response(True, message, data)
