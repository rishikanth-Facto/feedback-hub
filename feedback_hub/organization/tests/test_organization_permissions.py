import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization import service
from feedback_hub.organization.tests.helpers import make_user


class TestOrganizationPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("perm-admin@example.com")
		cls.developer = make_user("perm-developer@example.com")
		cls.outsider = make_user("perm-outsider@example.com")

	def setUp(self):
		frappe.set_user(self.admin.name)
		self.org = service.create_organization("Permissions Test Org " + frappe.generate_hash(length=6))
		invite = service.invite_member(self.org["name"], self.developer.name, "Developer")
		frappe.db.set_value("Organization Member", invite["name"], "status", "Active")
		self.developer_membership = invite["name"]

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_admin_can_manage_invite_and_change_roles(self):
		frappe.set_user(self.admin.name)
		service.update_organization(self.org["name"], description="updated by admin")
		service.update_member(self.developer_membership, role="Moderator")
		new_invite = service.invite_member(self.org["name"], "perm-newperson@example.com", "Customer")
		self.assertEqual(new_invite["status"], "Pending")

	def test_developer_cannot_manage_or_invite(self):
		frappe.set_user(self.developer.name)
		with self.assertRaises(frappe.PermissionError):
			service.update_organization(self.org["name"], description="hacked")
		with self.assertRaises(frappe.PermissionError):
			service.invite_member(self.org["name"], "someone@example.com", "Customer")
		with self.assertRaises(frappe.PermissionError):
			service.update_member(self.developer_membership, role="Organization Admin")

	def test_developer_can_read_own_organization_and_membership(self):
		frappe.set_user(self.developer.name)
		org = service.get_organization(self.org["name"])
		self.assertEqual(org["name"], self.org["name"])

		members = service.list_members(self.org["name"])
		self.assertEqual(len(members), 1)
		self.assertEqual(members[0]["user"], self.developer.name)

	def test_outsider_has_no_access(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			service.get_organization(self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.list_members(self.org["name"])
		names = [o["name"] for o in service.list_organizations()]
		self.assertNotIn(self.org["name"], names)

	def test_guest_denied_everywhere_except_accept_invitation(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			service.get_organization(self.org["name"])

		# accept_invitation itself never raises for Guest - it returns a
		# guidance result instead (spec: organization-permissions).
		result = service.accept_invitation("some-token")
		self.assertIn(result["result"], ("invalid", "login_required", "signup_required"))
