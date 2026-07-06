import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackStatusManagement(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("status-admin@example.com")
		cls.product_owner = make_user("status-product-owner@example.com")
		cls.moderator = make_user("status-moderator@example.com")
		cls.developer = make_user("status-developer@example.com")
		cls.customer = make_user("status-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Status Test Org " + frappe.generate_hash(length=6))
		for user, role in (
			(self.product_owner, "Product Owner"),
			(self.moderator, "Moderator"),
			(self.developer, "Developer"),
			(self.customer, "Customer"),
		):
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Status Board")
		frappe.db.set_value("Product", self.board["product"], "product_owner", self.product_owner.name)
		self.item = service.create_feedback(self.board["name"], "Movable item", description="Please add this.")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_organization_admin_can_move_status_to_anything(self):
		result = service.move_status(self.item["name"], "Planned")
		self.assertEqual(result["status"], "Planned")

	def test_moderator_runs_the_moderation_lifecycle(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		result = service.move_status(self.item["name"], "Under Review")
		self.assertEqual(result["status"], "Under Review")

		result = service.move_status(self.item["name"], "Approved")
		self.assertEqual(result["status"], "Approved")

	def test_moderator_can_reject_instead_of_approve(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		service.move_status(self.item["name"], "Under Review")
		result = service.move_status(self.item["name"], "Rejected")
		self.assertEqual(result["status"], "Rejected")

	def test_moderator_cannot_skip_into_the_roadmap_lifecycle(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.move_status(self.item["name"], "Planned")

	def test_moderator_cannot_act_once_item_reaches_roadmap_lifecycle(self):
		service.move_status(self.item["name"], "Under Review")
		service.move_status(self.item["name"], "Approved")

		switch_to_organization(self.moderator.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.move_status(self.item["name"], "Planned")

	def test_product_owner_runs_the_roadmap_lifecycle(self):
		# Only reachable once Moderation has approved it (design.md Decision 14).
		service.move_status(self.item["name"], "Under Review")
		service.move_status(self.item["name"], "Approved")

		switch_to_organization(self.product_owner.name, self.org["name"])
		for target in ("Planned", "In Progress", "Released", "Closed"):
			result = service.move_status(self.item["name"], target)
			self.assertEqual(result["status"], target)

	def test_product_owner_cannot_run_moderation_transitions(self):
		switch_to_organization(self.product_owner.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.move_status(self.item["name"], "Under Review")

	def test_product_owner_cannot_move_status_for_product_they_do_not_own(self):
		service.move_status(self.item["name"], "Under Review")
		service.move_status(self.item["name"], "Approved")

		other_owner = make_user("status-other-product-owner@example.com")
		add_active_member(self.org["name"], self.admin.name, other_owner.name, "Product Owner")
		switch_to_organization(other_owner.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.move_status(self.item["name"], "Planned")

	def test_developer_and_customer_cannot_move_status(self):
		for user in (self.developer, self.customer):
			switch_to_organization(user.name, self.org["name"])
			with self.assertRaises(frappe.PermissionError):
				service.move_status(self.item["name"], "Under Review")

	def test_invalid_target_status_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.move_status(self.item["name"], "Cancelled")
