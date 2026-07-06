import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackEditWindow(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("edit-admin@example.com")
		cls.customer = make_user("edit-customer@example.com")
		cls.other_customer = make_user("edit-other-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Edit Window Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.admin.name, self.customer.name, "Customer")
		add_active_member(self.org["name"], self.admin.name, self.other_customer.name, "Customer")
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Edit Window Board")

		switch_to_organization(self.customer.name, self.org["name"])
		self.item = service.create_feedback(self.board["name"], "Owned item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_owner_can_edit_while_new(self):
		result = service.update_feedback(self.item["name"], title="Edited title")
		self.assertEqual(result["title"], "Edited title")

	def test_owner_can_delete_while_new(self):
		service.delete_feedback(self.item["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_feedback(self.item["name"])

	def test_owner_cannot_edit_after_status_moves_forward(self):
		switch_to_organization(self.admin.name, self.org["name"])
		service.move_status(self.item["name"], "Under Review")

		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.update_feedback(self.item["name"], title="Too late")

	def test_owner_cannot_delete_after_status_moves_forward(self):
		switch_to_organization(self.admin.name, self.org["name"])
		service.move_status(self.item["name"], "Under Review")

		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_other_customer_cannot_edit_or_delete(self):
		switch_to_organization(self.other_customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.update_feedback(self.item["name"], title="Not mine")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_organization_admin_can_edit_and_delete_regardless_of_status(self):
		switch_to_organization(self.admin.name, self.org["name"])
		service.move_status(self.item["name"], "Released")
		result = service.update_feedback(self.item["name"], title="Admin edit")
		self.assertEqual(result["title"], "Admin edit")
		service.delete_feedback(self.item["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_feedback(self.item["name"])
