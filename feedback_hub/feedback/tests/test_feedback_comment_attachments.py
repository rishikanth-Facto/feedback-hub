import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import (
	MAX_COMMENT_ATTACHMENT_SIZE_BYTES,
	MAX_COMMENT_ATTACHMENTS,
	_add_comment_attachment,
	_create_comment,
	_remove_comment_attachment,
)
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackCommentAttachments(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("att-owner@example.com")
		cls.other_user = make_user("att-other@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Attachment Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.other_user.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Attachment Board")
		self.item = service.create_feedback(self.board["name"], "Attachable item", description="please")
		self.comment = _create_comment(self.item["name"], "Comment with attachments")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_add_within_limit(self):
		result = _add_comment_attachment(self.comment.name, "screenshot.png", b"fake-png-bytes")
		self.assertEqual(result["filename"], "screenshot.png")
		self.assertEqual(result["mime_type"], "image/png")
		self.assertIsNotNone(result["preview_url"])
		self.assertEqual(result["preview_url"], result["download_url"])

	def test_reject_beyond_max_attachments(self):
		for i in range(MAX_COMMENT_ATTACHMENTS):
			_add_comment_attachment(self.comment.name, f"file{i}.png", b"data")
		with self.assertRaises(frappe.ValidationError):
			_add_comment_attachment(self.comment.name, "one-too-many.png", b"data")

	def test_reject_disallowed_extension(self):
		with self.assertRaises(frappe.ValidationError):
			_add_comment_attachment(self.comment.name, "malware.exe", b"data")

	def test_reject_oversized_file(self):
		with self.assertRaises(frappe.ValidationError):
			_add_comment_attachment(self.comment.name, "huge.png", b"x" * (MAX_COMMENT_ATTACHMENT_SIZE_BYTES + 1))

	def test_video_types_accepted(self):
		for ext in ("mp4", "webm", "mov"):
			result = _add_comment_attachment(self.comment.name, f"clip.{ext}", b"fake-video-bytes")
			self.assertTrue(result["filename"].endswith(ext))

	def test_remove_deletes_child_row_and_file(self):
		added = _add_comment_attachment(self.comment.name, "to-remove.png", b"data")
		comment_doc = frappe.get_doc("Feedback Comment", self.comment.name)
		file_name = comment_doc.attachments[0].file

		_remove_comment_attachment(self.comment.name, added["name"])

		comment_doc.reload()
		self.assertEqual(len(comment_doc.attachments), 0)
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_non_author_cannot_attach_or_remove(self):
		switch_to_organization(self.other_user.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_add_comment_attachment(self.comment.name, "sneaky.png", b"data")

		switch_to_organization(self.owner.name, self.org["name"])
		added = _add_comment_attachment(self.comment.name, "owned.png", b"data")

		switch_to_organization(self.other_user.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_remove_comment_attachment(self.comment.name, added["name"])
