import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization import service
from feedback_hub.organization.tests.helpers import make_user


class TestOrganizationMember(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("member-admin@example.com")
		cls.developer = make_user("member-developer@example.com")
		cls.newbie_email = "member-newbie@example.com"

	def setUp(self):
		frappe.set_user(self.admin.name)
		self.org = service.create_organization("Membership Test Org " + frappe.generate_hash(length=6))

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_invite_existing_user_creates_pending_membership(self):
		invite = service.invite_member(self.org["name"], self.developer.name, "Developer")
		self.assertEqual(invite["status"], "Pending")
		self.assertEqual(invite["user"], self.developer.name)

	def test_invite_non_existent_user_stores_invited_email(self):
		invite = service.invite_member(self.org["name"], self.newbie_email, "Customer")
		self.assertEqual(invite["status"], "Pending")
		self.assertIsNone(invite["user"])
		row = frappe.db.get_value("Organization Member", invite["name"], "invited_email")
		self.assertEqual(row, self.newbie_email)

	def test_duplicate_pending_invite_rejected(self):
		service.invite_member(self.org["name"], self.developer.name, "Developer")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.invite_member(self.org["name"], self.developer.name, "Moderator")

	def test_invite_of_active_member_rejected(self):
		with self.assertRaises(frappe.DuplicateEntryError):
			service.invite_member(self.org["name"], self.admin.name, "Developer")

	def test_role_update_by_admin_succeeds(self):
		invite = service.invite_member(self.org["name"], self.developer.name, "Developer")
		frappe.db.set_value("Organization Member", invite["name"], "status", "Active")
		updated = service.update_member(invite["name"], role="Moderator")
		self.assertEqual(updated["role"], "Moderator")

	def test_role_update_by_non_admin_rejected(self):
		invite = service.invite_member(self.org["name"], self.developer.name, "Developer")
		frappe.db.set_value("Organization Member", invite["name"], "status", "Active")
		frappe.set_user(self.developer.name)
		with self.assertRaises(frappe.PermissionError):
			service.update_member(invite["name"], role="Moderator")

	def test_remove_member_succeeds(self):
		invite = service.invite_member(self.org["name"], self.developer.name, "Developer")
		service.remove_member(invite["name"])
		self.assertFalse(frappe.db.exists("Organization Member", invite["name"]))

	def test_last_active_admin_cannot_be_removed(self):
		admin_membership = frappe.db.get_value(
			"Organization Member", {"organization": self.org["name"], "user": self.admin.name}, "name"
		)
		with self.assertRaises(frappe.ValidationError):
			service.remove_member(admin_membership)

	def test_last_active_admin_cannot_be_demoted(self):
		admin_membership = frappe.db.get_value(
			"Organization Member", {"organization": self.org["name"], "user": self.admin.name}, "name"
		)
		with self.assertRaises(frappe.ValidationError):
			service.update_member(admin_membership, role="Developer")

	def test_second_admin_allows_first_to_be_demoted(self):
		invite = service.invite_member(self.org["name"], self.developer.name, "Organization Admin")
		frappe.db.set_value("Organization Member", invite["name"], "status", "Active")
		admin_membership = frappe.db.get_value(
			"Organization Member", {"organization": self.org["name"], "user": self.admin.name}, "name"
		)
		updated = service.update_member(admin_membership, role="Developer")
		self.assertEqual(updated["role"], "Developer")
