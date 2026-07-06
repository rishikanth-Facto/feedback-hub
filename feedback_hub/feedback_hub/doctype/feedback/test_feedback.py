import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedback(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("feedback-owner@example.com")
		cls.customer = make_user("feedback-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Feedback Test Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.customer.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.public_board = make_board(self.org["name"], "Public Board")
		self.private_board = make_board(self.org["name"], "Private Board", visibility="Private")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_submission_success(self):
		item = service.create_feedback(self.public_board["name"], "Add dark mode", description="please")
		self.assertEqual(item["status"], "New")
		self.assertEqual(item["submitted_by"], self.owner.name)
		self.assertEqual(item["vote_count"], 0)

	def test_missing_title_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_feedback(self.public_board["name"], "")

	def test_status_forced_on_creation_even_if_supplied(self):
		doc = frappe.get_doc(
			{
				"doctype": "Feedback",
				"title": "sneaky status",
				"description": "please",
				"board": self.public_board["name"],
				"status": "Released",
			}
		)
		doc.insert()
		self.assertEqual(doc.status, "New")

	def test_submission_without_board_read_access_rejected(self):
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.create_feedback(self.private_board["name"], "Sneaky", description="please")

	def test_customer_sees_feedback_only_on_public_board(self):
		service.create_feedback(self.public_board["name"], "Public item", description="please")
		service.create_feedback(self.private_board["name"], "Private item", description="please")

		switch_to_organization(self.customer.name, self.org["name"])
		public_result = service.list_feedback(board=self.public_board["name"])
		self.assertEqual(len(public_result["feedback"]), 1)

		with self.assertRaises(frappe.PermissionError):
			service.list_feedback(board=self.private_board["name"])

	def test_get_non_existent_feedback_rejected(self):
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_feedback("FDB-doesnotexist")
