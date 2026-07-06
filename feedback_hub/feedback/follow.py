import frappe
from frappe import _

from feedback_hub.feedback.events import emit_event
from feedback_hub.feedback.permissions import require_board_read
from feedback_hub.feedback.timeline import record_activity
from feedback_hub.organization.api import handle_errors
from feedback_hub.utils import api_response, require_login


def _toggle_follow(feedback):
	doc = frappe.get_doc("Feedback", feedback)  # raises DoesNotExistError if missing
	# No archived-feedback restriction here - only "cannot follow deleted
	# feedback" is specified for following (design.md Decision 4's scope),
	# unlike voting/commenting which also block on an archived Product.
	require_board_read(doc.board)

	existing = frappe.db.exists("Feedback Follower", {"feedback": feedback, "user": frappe.session.user})
	if existing:
		# Hard delete - Feedback Follower has no is_deleted field (design.md
		# Decision 4); has_permission_feedback_follower's delete branch only
		# allows a user to remove their own follow, so ignore_permissions=True
		# here only skips the redundant re-check, same bypass-after-explicit-
		# check pattern as toggle_vote.
		frappe.delete_doc("Feedback Follower", existing, ignore_permissions=True)
		following = False
	else:
		frappe.get_doc({"doctype": "Feedback Follower", "feedback": feedback, "user": frappe.session.user}).insert()
		following = True

	follower_count = frappe.db.count("Feedback Follower", {"feedback": feedback})
	record_activity(feedback, "Followed Feedback" if following else "Unfollowed Feedback")
	emit_event("follow", doc, following=following)
	return {"feedback": feedback, "following": following, "follower_count": follower_count}


@frappe.whitelist(methods=["POST"])
@handle_errors
def toggle_follow(feedback=None):
	require_login()
	data = _toggle_follow(feedback)
	message = _("Now following this feedback item.") if data.get("following") else _("Unfollowed this feedback item.")
	return api_response(True, message, data)
