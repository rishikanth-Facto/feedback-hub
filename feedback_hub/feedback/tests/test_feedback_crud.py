import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackCrud(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("crud-admin@example.com")
		cls.customer = make_user("crud-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Crud Test Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.admin.name, self.customer.name, "Customer")
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Crud Board")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_create_with_full_fields(self):
		item = service.create_feedback(
			self.board["name"], "Add dark mode", description="please", category="Bug", priority="High", is_anonymous=1
		)
		self.assertEqual(item["category"], "Bug")
		self.assertEqual(item["priority"], "High")
		self.assertTrue(item["is_anonymous"])
		self.assertEqual(item["board"], self.board["name"])
		self.assertEqual(item["product"], self.board["product"])
		self.assertEqual(item["organization"], self.org["name"])

	def test_defaults_applied_when_omitted(self):
		item = service.create_feedback(self.board["name"], "Minimal item", description="please")
		self.assertEqual(item["status"], "New")
		self.assertEqual(item["priority"], "Medium")
		self.assertEqual(item["category"], "Other")
		self.assertFalse(item["is_anonymous"])

	def test_missing_description_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_feedback(self.board["name"], "No description")

	def test_invalid_category_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_feedback(self.board["name"], "Bad category", description="please", category="NotACategory")

	def test_invalid_priority_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_feedback(self.board["name"], "Bad priority", description="please", priority="Critical")

	def test_organization_and_product_are_derived_not_client_supplied(self):
		other_org = make_active_organization(self.admin.name, "Other Org " + frappe.generate_hash(length=6))
		other_board = make_board(other_org["name"], "Other Org Board")
		switch_to_organization(self.admin.name, self.org["name"])
		doc = frappe.get_doc(
			{
				"doctype": "Feedback",
				"title": "Sneaky org",
				"description": "please",
				"board": self.board["name"],
				"organization": other_org["name"],
				"product": other_board["product"],
			}
		)
		doc.insert()
		self.assertEqual(doc.organization, self.org["name"])
		self.assertEqual(doc.product, self.board["product"])

	def test_get_update_delete_roundtrip(self):
		item = service.create_feedback(self.board["name"], "Roundtrip item", description="please")
		fetched = service.get_feedback(item["name"])
		self.assertEqual(fetched["title"], "Roundtrip item")

		updated = service.update_feedback(item["name"], title="Updated title")
		self.assertEqual(updated["title"], "Updated title")

		service.delete_feedback(item["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_feedback(item["name"])
