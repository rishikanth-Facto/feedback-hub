import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization import context
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product import api, service
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestProductBoardPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("pb-admin@example.com")
		cls.product_owner = make_user("pb-product-owner@example.com")
		cls.moderator = make_user("pb-moderator@example.com")
		cls.developer = make_user("pb-developer@example.com")
		cls.customer = make_user("pb-customer@example.com")
		cls.outsider = make_user("pb-outsider@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "PB Perm Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.admin.name, self.product_owner.name, "Product Owner")
		add_active_member(self.org["name"], self.admin.name, self.moderator.name, "Moderator")
		add_active_member(self.org["name"], self.admin.name, self.developer.name, "Developer")
		add_active_member(self.org["name"], self.admin.name, self.customer.name, "Customer")

		# The invite calls above each hop through frappe.set_user(admin), which
		# resets session data (frappe/__init__.py:set_user) - restore admin's
		# active organization before creating fixtures.
		switch_to_organization(self.admin.name, self.org["name"])
		self.product = service.create_product("Perm Test Product")
		self.public_board = service.create_board(self.product["name"], "Public Board", "Public")
		self.private_board = service.create_board(self.product["name"], "Private Board", "Private")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_organization_admin_and_product_owner_have_full_crud(self):
		for user in (self.admin, self.product_owner):
			switch_to_organization(user.name, self.org["name"])
			product = service.create_product("CRUD Product " + frappe.generate_hash(length=6))
			service.update_product(product["name"], description="updated")
			board = service.create_board(product["name"], "CRUD Board", "Public")
			service.update_board(board["name"], description="updated")
			service.delete_board(board["name"])
			service.delete_product(product["name"])

	def test_moderator_read_and_update_boards_only_no_create_delete_no_products(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		service.get_board(self.public_board["name"])
		service.update_board(self.public_board["name"], description="moderated")

		with self.assertRaises(frappe.PermissionError):
			service.create_board(self.product["name"], "Mod Created Board", "Public")
		with self.assertRaises(frappe.PermissionError):
			service.delete_board(self.public_board["name"])
		with self.assertRaises(frappe.PermissionError):
			service.get_product(self.product["name"])
		names = [p["name"] for p in service.list_products()]
		self.assertNotIn(self.product["name"], names)

	def test_developer_read_only_boards_no_products(self):
		switch_to_organization(self.developer.name, self.org["name"])
		service.get_board(self.public_board["name"])
		service.get_board(self.private_board["name"])

		with self.assertRaises(frappe.PermissionError):
			service.update_board(self.public_board["name"], description="dev edit")
		with self.assertRaises(frappe.PermissionError):
			service.create_board(self.product["name"], "Dev Created Board", "Public")
		with self.assertRaises(frappe.PermissionError):
			service.delete_board(self.public_board["name"])
		with self.assertRaises(frappe.PermissionError):
			service.get_product(self.product["name"])
		names = [p["name"] for p in service.list_products()]
		self.assertNotIn(self.product["name"], names)

	def test_customer_read_only_public_boards_no_products(self):
		switch_to_organization(self.customer.name, self.org["name"])
		service.get_board(self.public_board["name"])

		with self.assertRaises(frappe.PermissionError):
			service.get_board(self.private_board["name"])

		board_names = [b["name"] for b in service.list_boards(self.product["name"])]
		self.assertIn(self.public_board["name"], board_names)
		self.assertNotIn(self.private_board["name"], board_names)

		with self.assertRaises(frappe.PermissionError):
			service.update_board(self.public_board["name"], description="customer edit")
		with self.assertRaises(frappe.PermissionError):
			service.create_board(self.product["name"], "Customer Created Board", "Public")
		with self.assertRaises(frappe.PermissionError):
			service.delete_board(self.public_board["name"])
		with self.assertRaises(frappe.PermissionError):
			service.get_product(self.product["name"])
		names = [p["name"] for p in service.list_products()]
		self.assertNotIn(self.product["name"], names)

	def test_customer_sees_products_with_at_least_one_public_board(self):
		switch_to_organization(self.customer.name, self.org["name"])
		names = [p["name"] for p in service.list_visible_products()]
		self.assertIn(self.product["name"], names)

	def test_customer_does_not_see_products_with_only_private_boards(self):
		switch_to_organization(self.admin.name, self.org["name"])
		private_only_product = service.create_product("Private Only Product " + frappe.generate_hash(length=6))
		service.create_board(private_only_product["name"], "Only Private Board", "Private")

		switch_to_organization(self.customer.name, self.org["name"])
		names = [p["name"] for p in service.list_visible_products()]
		self.assertNotIn(private_only_product["name"], names)

	def test_organization_admin_sees_products_with_only_private_boards_too(self):
		switch_to_organization(self.admin.name, self.org["name"])
		private_only_product = service.create_product("Admin Visible Private Product " + frappe.generate_hash(length=6))
		service.create_board(private_only_product["name"], "Only Private Board 2", "Private")

		names = [p["name"] for p in service.list_visible_products()]
		self.assertIn(private_only_product["name"], names)

	def test_switching_organizations_changes_visible_products_and_boards(self):
		make_active_organization(self.admin.name, "PB Perm Org B " + frappe.generate_hash(length=6))
		names = [p["name"] for p in service.list_products()]
		self.assertNotIn(self.product["name"], names)

		switch_to_organization(self.admin.name, self.org["name"])
		names = [p["name"] for p in service.list_products()]
		self.assertIn(self.product["name"], names)

	def test_no_active_organization_yields_no_access(self):
		frappe.set_user(self.admin.name)
		self.assertIsNone(context.get_active_organization())
		with self.assertRaises(frappe.ValidationError):
			service.list_products()
		with self.assertRaises(frappe.ValidationError):
			service.list_boards()

	def test_direct_id_access_to_other_organizations_product_and_board_rejected_even_for_its_admin(self):
		# self.admin is Organization Admin of a brand-new second organization
		# too (creator), but self.org is no longer active - direct id access
		# must still be rejected (design.md Decision 3; spec: product-board-
		# permissions "Cross-Organization Access Is Prevented").
		make_active_organization(self.admin.name, "PB Perm Org C " + frappe.generate_hash(length=6))
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_product(self.product["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_board(self.public_board["name"])

	def test_non_member_of_this_organization_has_no_access(self):
		make_active_organization(self.outsider.name, "Outsider Org " + frappe.generate_hash(length=6))
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_product(self.product["name"])
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_board(self.public_board["name"])

	def test_guest_rejected_on_every_endpoint(self):
		frappe.set_user("Guest")

		for res in (
			api.create_product(product_name="Guest Product"),
			api.list_products(),
			api.get_product(product=self.product["name"]),
			api.update_product(product=self.product["name"], description="hacked"),
			api.delete_product(product=self.product["name"]),
			api.create_board(product=self.product["name"], board_name="Guest Board", visibility="Public"),
			api.list_boards(),
			api.get_board(board=self.public_board["name"]),
			api.update_board(board=self.public_board["name"], description="hacked"),
			api.delete_board(board=self.public_board["name"]),
		):
			self.assertFalse(res["success"])
