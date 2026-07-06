import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackAttachments(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("attach-owner@example.com")
		cls.other_customer = make_user("attach-other-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Attach Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.other_customer.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Attach Board")
		self.item = service.create_feedback(self.board["name"], "Attachable item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_add_attachment_within_limit(self):
		result = service.add_attachment(self.item["name"], "notes.txt", b"hello world")
		self.assertEqual(result["file_name"], "notes.txt")
		self.assertEqual(result["file_type"], "txt")
		self.assertEqual(result["file_size"], len(b"hello world"))

	def test_exceeding_attachment_limit_rejected(self):
		for i in range(5):
			service.add_attachment(self.item["name"], f"file{i}.txt", b"data")
		with self.assertRaises(frappe.ValidationError):
			service.add_attachment(self.item["name"], "one-too-many.txt", b"data")

	def test_disallowed_extension_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.add_attachment(self.item["name"], "malware.exe", b"data")

	def test_oversized_file_rejected(self):
		big_content = b"x" * (5 * 1024 * 1024 + 1)
		with self.assertRaises(frappe.ValidationError):
			service.add_attachment(self.item["name"], "big.txt", big_content)

	def test_remove_attachment_deletes_row_and_file(self):
		service.add_attachment(self.item["name"], "notes.txt", b"hello world")
		doc = frappe.get_doc("Feedback", self.item["name"])
		row = doc.attachments[0]
		file_name = row.file

		service.remove_attachment(self.item["name"], row.name)

		doc.reload()
		self.assertEqual(len(doc.attachments), 0)
		self.assertFalse(frappe.db.exists("File", file_name))

	def test_remove_attachment_without_access_rejected(self):
		service.add_attachment(self.item["name"], "notes.txt", b"hello world")
		doc = frappe.get_doc("Feedback", self.item["name"])
		row_name = doc.attachments[0].name

		switch_to_organization(self.other_customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.remove_attachment(self.item["name"], row_name)
