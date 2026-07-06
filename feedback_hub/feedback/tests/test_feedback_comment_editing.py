import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import _create_comment, _update_comment
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackCommentEditing(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("edit-owner@example.com")
		cls.other_user = make_user("edit-other@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Edit Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.other_user.name, "Moderator")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Edit Board")
		self.item = service.create_feedback(self.board["name"], "Editable item", description="please")
		self.comment = _create_comment(self.item["name"], "Original text")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_author_edits_own_comment(self):
		updated = _update_comment(self.comment.name, "Edited text")
		self.assertEqual(updated["content"], "Edited text")
		self.assertTrue(updated["edited"])
		self.assertIsNotNone(updated["edited_at"])
		self.assertEqual(updated["edited_by"], self.owner.name)

	def test_non_author_edit_rejected_regardless_of_role(self):
		# other_user is a Moderator - moderators may delete but never silently
		# edit someone else's comment (design.md Decision 7).
		switch_to_organization(self.other_user.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_update_comment(self.comment.name, "Hijacked text")

	def test_edit_history_retained_in_version_log(self):
		_update_comment(self.comment.name, "Edited text")
		versions = frappe.get_all(
			"Version", filters={"ref_doctype": "Feedback Comment", "docname": self.comment.name}
		)
		self.assertTrue(len(versions) >= 1)
