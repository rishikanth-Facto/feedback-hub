import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import _create_comment, _delete_comment, _update_comment
from feedback_hub.feedback.follow import _toggle_follow
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.feedback.vote import _toggle_vote
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization


class TestFeedbackEngagementTimeline(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("timeline-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Timeline Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "Timeline Board")
		self.item = service.create_feedback(self.board["name"], "Timeline item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _timeline_texts(self):
		return frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Feedback", "reference_name": self.item["name"], "comment_type": "Info"},
			pluck="content",
		)

	def test_vote_add_and_remove_produce_timeline_entries(self):
		_toggle_vote(self.item["name"])
		_toggle_vote(self.item["name"])
		texts = self._timeline_texts()
		self.assertIn("Vote Added", texts)
		self.assertIn("Vote Removed", texts)

	def test_comment_add_edit_delete_produce_timeline_entries(self):
		comment = _create_comment(self.item["name"], "Original")
		_update_comment(comment.name, "Edited")
		_delete_comment(comment.name)
		texts = self._timeline_texts()
		self.assertIn("Comment Added", texts)
		self.assertIn("Comment Edited", texts)
		self.assertIn("Comment Deleted", texts)

	def test_reply_produces_distinct_timeline_entry(self):
		root = _create_comment(self.item["name"], "Root")
		_create_comment(self.item["name"], "A reply", parent_comment=root.name)
		texts = self._timeline_texts()
		self.assertIn("Comment Added", texts)
		self.assertIn("Reply Added", texts)

	def test_follow_and_unfollow_produce_timeline_entries(self):
		_toggle_follow(self.item["name"])
		_toggle_follow(self.item["name"])
		texts = self._timeline_texts()
		self.assertIn("Followed Feedback", texts)
		self.assertIn("Unfollowed Feedback", texts)
