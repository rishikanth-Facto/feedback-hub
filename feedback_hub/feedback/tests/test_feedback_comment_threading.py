import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import MAX_COMMENT_LENGTH, _create_comment
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization


class TestFeedbackCommentThreading(FrappeTestCase):
	"""Covers task 14.3 (create/reply/threading/mentions/length validation) -
	named distinctly from the pre-existing test_feedback_commenting.py (which
	exercises the legacy service.add_comment re-export and must keep passing
	unmodified per task 14.12)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("thread-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Thread Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "Thread Board")
		self.item = service.create_feedback(self.board["name"], "Threadable item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_create_root_comment(self):
		doc = _create_comment(self.item["name"], "Root comment")
		self.assertEqual(doc.comment_text, "Root comment")
		self.assertIsNone(doc.parent_comment)

	def test_create_reply(self):
		root = _create_comment(self.item["name"], "Root")
		reply = _create_comment(self.item["name"], "A reply", parent_comment=root.name)
		self.assertEqual(reply.parent_comment, root.name)

	def test_unlimited_depth_nesting(self):
		parent = _create_comment(self.item["name"], "Level 0")
		for depth in range(1, 6):
			parent = _create_comment(self.item["name"], f"Level {depth}", parent_comment=parent.name)
		# The deepest reply's parent chain should be 5 levels below the root.
		count = 0
		node = parent
		while node.parent_comment:
			node = frappe.get_doc("Feedback Comment", node.parent_comment)
			count += 1
		self.assertEqual(count, 5)

	def test_parent_comment_must_match_feedback(self):
		other_board = make_board(self.org["name"], "Other Thread Board")
		other_item = service.create_feedback(other_board["name"], "Other item", description="please")
		other_root = _create_comment(other_item["name"], "Other root")

		with self.assertRaises(frappe.ValidationError):
			_create_comment(self.item["name"], "Mismatched reply", parent_comment=other_root.name)

	def test_nonexistent_parent_comment_rejected(self):
		with self.assertRaises(frappe.DoesNotExistError):
			_create_comment(self.item["name"], "Orphan reply", parent_comment="FDC-doesnotexist")

	def test_content_length_validation(self):
		with self.assertRaises(frappe.ValidationError):
			_create_comment(self.item["name"], "x" * (MAX_COMMENT_LENGTH + 1))

	def test_markdown_plaintext_and_mentions_stored_verbatim(self):
		text = "**bold** _italic_ plain text @someuser mention"
		doc = _create_comment(self.item["name"], text)
		self.assertEqual(doc.comment_text, text)
