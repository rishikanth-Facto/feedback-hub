import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization import context, service
from feedback_hub.organization.tests.helpers import make_user


class TestSwitchOrganization(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = make_user("switch-user@example.com")
		cls.outsider = make_user("switch-outsider@example.com")

	def setUp(self):
		frappe.set_user(self.user.name)
		self.org_a = service.create_organization("Switch Org A " + frappe.generate_hash(length=6))
		self.org_b = service.create_organization("Switch Org B " + frappe.generate_hash(length=6))

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_valid_switch_is_resolved_on_next_call(self):
		service.switch_organization(self.org_a["name"])
		self.assertEqual(context.get_active_organization(), self.org_a["name"])

		service.switch_organization(self.org_b["name"])
		self.assertEqual(context.get_active_organization(), self.org_b["name"])

	def test_switch_to_non_member_organization_rejected(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			service.switch_organization(self.org_a["name"])

	def test_switch_to_inactive_organization_rejected(self):
		frappe.db.set_value("Organization", self.org_a["name"], "status", "Inactive")
		with self.assertRaises(frappe.ValidationError):
			service.switch_organization(self.org_a["name"])

	def test_revoked_membership_invalidates_active_context(self):
		service.switch_organization(self.org_a["name"])
		self.assertEqual(context.get_active_organization(), self.org_a["name"])

		membership = frappe.db.get_value(
			"Organization Member", {"organization": self.org_a["name"], "user": self.user.name}, "name"
		)
		frappe.db.set_value("Organization Member", membership, "status", "Suspended")

		self.assertIsNone(context.get_active_organization())

	def test_sole_organization_is_implicitly_active_without_switching(self):
		# A user with exactly one organization has no org-switcher to click
		# (org_switcher.js hides itself below 2 memberships) - without this,
		# they could never reach any organization-scoped feature.
		solo_user = make_user("switch-solo-user@example.com")
		frappe.set_user(solo_user.name)
		org = service.create_organization("Solo Org " + frappe.generate_hash(length=6))
		self.assertEqual(context.get_active_organization(), org["name"])

	def test_no_active_organization_when_caller_has_multiple_and_never_switched(self):
		# self.user already has org_a and org_b from setUp and hasn't called
		# switch_organization yet in this test - with 2+ memberships and no
		# explicit selection, there is no unambiguous default.
		self.assertIsNone(context.get_active_organization())
