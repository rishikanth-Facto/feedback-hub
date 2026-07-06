import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization import service
from feedback_hub.organization.tests.helpers import make_user


class TestOrganization(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("org-owner@example.com")

	def setUp(self):
		frappe.set_user(self.owner.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_create_organization_success(self):
		org = service.create_organization("Test Org Alpha", description="hello")
		self.assertEqual(org["organization_name"], "Test Org Alpha")
		self.assertEqual(org["slug"], "test-org-alpha")
		self.assertEqual(org["status"], "Active")
		self.assertEqual(org["organization_owner"], self.owner.name)

		membership = frappe.db.get_value(
			"Organization Member",
			{"organization": org["name"], "user": self.owner.name},
			["role", "status"],
			as_dict=True,
		)
		self.assertEqual(membership.role, "Organization Admin")
		self.assertEqual(membership.status, "Active")

	def test_slug_collision_gets_numeric_suffix(self):
		org1 = service.create_organization("Collide Corp")
		# Different name, same slugified form - must not collide.
		org2 = service.create_organization("Collide  Corp!!")
		self.assertNotEqual(org1["slug"], org2["slug"])
		self.assertTrue(org2["slug"].startswith("collide-corp"))

	def test_duplicate_name_rejected(self):
		service.create_organization("Duplicate Org")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.create_organization("Duplicate Org")

	def test_missing_name_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_organization("")

	def test_update_organization(self):
		org = service.create_organization("Updatable Org")
		updated = service.update_organization(org["name"], description="new desc")
		self.assertEqual(updated["description"], "new desc")
		# slug must not change on rename (design.md Decision 2)
		renamed = service.update_organization(org["name"], organization_name="Updatable Org Renamed")
		self.assertEqual(renamed["slug"], org["slug"])

	def test_update_to_duplicate_name_rejected(self):
		service.create_organization("Name One")
		org2 = service.create_organization("Name Two")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.update_organization(org2["name"], organization_name="Name One")

	def test_delete_blocked_by_other_active_members(self):
		org = service.create_organization("Guarded Org")
		other_admin = make_user("guarded-org-second-admin@example.com")
		invite = service.invite_member(org["name"], other_admin.name, "Organization Admin")
		frappe.db.set_value("Organization Member", invite["name"], "status", "Active")

		with self.assertRaises(frappe.LinkExistsError):
			service.delete_organization(org["name"], force=False)
		self.assertEqual(frappe.db.get_value("Organization", org["name"], "status"), "Active")

	def test_soft_delete_when_caller_is_sole_active_member(self):
		org = service.create_organization("Emptyable Org")
		result = service.delete_organization(org["name"], force=False)
		self.assertFalse(result["deleted"])
		self.assertEqual(frappe.db.get_value("Organization", org["name"], "status"), "Inactive")

	def test_force_delete_removes_organization_and_members(self):
		org = service.create_organization("Force Deletable Org")
		result = service.delete_organization(org["name"], force=True)
		self.assertTrue(result["deleted"])
		self.assertFalse(frappe.db.exists("Organization", org["name"]))
		self.assertEqual(frappe.db.count("Organization Member", {"organization": org["name"]}), 0)

	def test_non_member_cannot_read_organization(self):
		org = service.create_organization("Private Org")
		outsider = make_user("outsider@example.com")
		frappe.set_user(outsider.name)
		with self.assertRaises(frappe.PermissionError):
			service.get_organization(org["name"])

	def test_non_member_excluded_from_listing(self):
		org = service.create_organization("Listed Org")
		outsider = make_user("outsider2@example.com")
		frappe.set_user(outsider.name)
		names = [o["name"] for o in service.list_organizations()]
		self.assertNotIn(org["name"], names)
