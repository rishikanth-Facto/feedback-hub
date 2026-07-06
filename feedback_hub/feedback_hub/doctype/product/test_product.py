import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product import service
from feedback_hub.product.tests.helpers import make_active_organization


class TestProduct(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("product-owner-user@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Product Test Org " + frappe.generate_hash(length=6))

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_create_product_success(self):
		product = service.create_product("Mobile App", description="hello")
		self.assertEqual(product["product_name"], "Mobile App")
		self.assertEqual(product["slug"], "mobile-app")
		self.assertEqual(product["status"], "Active")
		self.assertEqual(product["organization"], self.org["name"])
		self.assertEqual(product["product_owner"], self.owner.name)

	def test_missing_name_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_product("")

	def test_duplicate_name_within_same_organization_rejected(self):
		service.create_product("Duplicate Product")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.create_product("Duplicate Product")

	def test_same_name_allowed_in_different_organization(self):
		service.create_product("Shared Name Product")
		other_org = make_active_organization(self.owner.name, "Second Org " + frappe.generate_hash(length=6))
		product = service.create_product("Shared Name Product")
		self.assertEqual(product["organization"], other_org["name"])

	def test_slug_collision_within_organization_gets_numeric_suffix(self):
		p1 = service.create_product("Collide Product")
		# Different name, same slugified form - must not collide.
		p2 = service.create_product("Collide  Product!!")
		self.assertNotEqual(p1["slug"], p2["slug"])
		self.assertTrue(p2["slug"].startswith("collide-product"))

	def test_identical_slug_allowed_across_organizations(self):
		p1 = service.create_product("Cross Org Product")
		make_active_organization(self.owner.name, "Third Org " + frappe.generate_hash(length=6))
		p2 = service.create_product("Cross Org Product")
		self.assertEqual(p1["slug"], p2["slug"])

	def test_update_product(self):
		product = service.create_product("Updatable Product")
		updated = service.update_product(product["name"], description="new desc")
		self.assertEqual(updated["description"], "new desc")
		# slug must not change on rename (design.md Decision 6)
		renamed = service.update_product(product["name"], product_name="Updatable Product Renamed")
		self.assertEqual(renamed["slug"], product["slug"])

	def test_update_to_duplicate_name_within_organization_rejected(self):
		service.create_product("Name One")
		p2 = service.create_product("Name Two")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.update_product(p2["name"], product_name="Name One")

	def test_archive_via_status_update(self):
		product = service.create_product("Archivable Product")
		archived = service.update_product(product["name"], status="Archived")
		self.assertEqual(archived["status"], "Archived")

	def test_invalid_status_rejected(self):
		product = service.create_product("Bad Status Product")
		with self.assertRaises(frappe.ValidationError):
			service.update_product(product["name"], status="Deleted")

	def test_delete_blocked_by_existing_boards(self):
		product = service.create_product("Guarded Product")
		service.create_board(product["name"], "General", "Public")
		with self.assertRaises(frappe.LinkExistsError):
			service.delete_product(product["name"], force=False)
		self.assertTrue(frappe.db.exists("Product", product["name"]))

	def test_delete_succeeds_with_no_boards(self):
		product = service.create_product("Emptyable Product")
		result = service.delete_product(product["name"], force=False)
		self.assertTrue(result["deleted"])
		self.assertFalse(frappe.db.exists("Product", product["name"]))

	def test_force_delete_cascades_to_boards(self):
		product = service.create_product("Force Deletable Product")
		service.create_board(product["name"], "General", "Public")
		result = service.delete_product(product["name"], force=True)
		self.assertTrue(result["deleted"])
		self.assertFalse(frappe.db.exists("Product", product["name"]))
		self.assertEqual(frappe.db.count("Board", {"product": product["name"]}), 0)

	def test_get_and_list_never_return_another_organizations_product(self):
		org_a_product = service.create_product("Org A Product")
		make_active_organization(self.owner.name, "Org B " + frappe.generate_hash(length=6))
		with self.assertRaises(frappe.DoesNotExistError):
			service.get_product(org_a_product["name"])
		names = [p["name"] for p in service.list_products()]
		self.assertNotIn(org_a_product["name"], names)
