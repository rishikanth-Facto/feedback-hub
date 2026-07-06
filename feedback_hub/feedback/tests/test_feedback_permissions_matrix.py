import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product import service as product_service
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackPermissionsMatrix(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("perm-admin@example.com")
		cls.product_owner = make_user("perm-product-owner@example.com")
		cls.other_product_owner = make_user("perm-other-product-owner@example.com")
		cls.moderator = make_user("perm-moderator@example.com")
		cls.developer = make_user("perm-developer@example.com")
		cls.customer = make_user("perm-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Perm Org " + frappe.generate_hash(length=6))
		for user, role in (
			(self.product_owner, "Product Owner"),
			(self.other_product_owner, "Product Owner"),
			(self.moderator, "Moderator"),
			(self.developer, "Developer"),
			(self.customer, "Customer"),
		):
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])

		self.product = product_service.create_product("Owned Product " + frappe.generate_hash(length=6))
		frappe.db.set_value("Product", self.product["name"], "product_owner", self.product_owner.name)
		self.board = product_service.create_board(self.product["name"], "Owned Board", "Public")

		self.other_product = product_service.create_product("Other Product " + frappe.generate_hash(length=6))
		frappe.db.set_value("Product", self.other_product["name"], "product_owner", self.other_product_owner.name)
		self.other_board = product_service.create_board(self.other_product["name"], "Other Board", "Public")

		self.item = service.create_feedback(self.board["name"], "Owned board item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_customer_can_create_and_read(self):
		switch_to_organization(self.customer.name, self.org["name"])
		item = service.create_feedback(self.board["name"], "Customer item", description="please")
		fetched = service.get_feedback(item["name"])
		self.assertEqual(fetched["name"], item["name"])

	def test_customer_cannot_edit_or_delete_others_feedback(self):
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.update_feedback(self.item["name"], title="Nope")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_moderator_can_read_and_write_but_not_delete(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		result = service.update_feedback(self.item["name"], title="Moderator edit")
		self.assertEqual(result["title"], "Moderator edit")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_product_owner_manages_feedback_for_owned_product(self):
		# Revised: Product Owner may edit feedback under products they own,
		# but never delete it (deleting customer feedback is an audit-trail
		# risk) - Delete stays Organization Admin/owner-while-New only.
		switch_to_organization(self.product_owner.name, self.org["name"])
		result = service.update_feedback(self.item["name"], title="Owner edit")
		self.assertEqual(result["title"], "Owner edit")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_product_owner_cannot_manage_feedback_for_other_product(self):
		other_item = service.create_feedback(self.other_board["name"], "Other board item", description="please")
		switch_to_organization(self.product_owner.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.update_feedback(other_item["name"], title="Not mine")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(other_item["name"])

	def test_organization_admin_full_access(self):
		result = service.update_feedback(self.item["name"], title="Admin edit")
		self.assertEqual(result["title"], "Admin edit")
		service.delete_feedback(self.item["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_feedback(self.item["name"])

	def test_developer_is_read_only(self):
		switch_to_organization(self.developer.name, self.org["name"])
		fetched = service.get_feedback(self.item["name"])
		self.assertEqual(fetched["name"], self.item["name"])
		with self.assertRaises(frappe.PermissionError):
			service.update_feedback(self.item["name"], title="Nope")
		with self.assertRaises(frappe.PermissionError):
			service.delete_feedback(self.item["name"])

	def test_cross_organization_access_rejected(self):
		other_org = make_active_organization(self.admin.name, "Outsider Org " + frappe.generate_hash(length=6))
		outsider = make_user("perm-outsider@example.com")
		add_active_member(other_org["name"], self.admin.name, outsider.name, "Customer")
		switch_to_organization(outsider.name, other_org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.get_feedback(self.item["name"])

	def test_cross_organization_list_excludes_other_organizations(self):
		other_org = make_active_organization(self.admin.name, "Outsider List Org " + frappe.generate_hash(length=6))
		outsider = make_user("perm-outsider-list@example.com")
		add_active_member(other_org["name"], self.admin.name, outsider.name, "Customer")
		switch_to_organization(outsider.name, other_org["name"])
		result = service.list_feedback()
		names = {item["name"] for item in result["feedback"]}
		self.assertNotIn(self.item["name"], names)
