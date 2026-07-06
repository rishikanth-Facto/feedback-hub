import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from feedback_hub.organization import service
from feedback_hub.organization.tests.helpers import make_user


class TestInvitation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("invite-admin@example.com")
		cls.invitee = make_user("invite-invitee@example.com")

	def setUp(self):
		frappe.set_user(self.admin.name)
		self.org = service.create_organization("Invitation Test Org " + frappe.generate_hash(length=6))

	def tearDown(self):
		frappe.set_user("Administrator")

	def _invite_and_get_token(self, email="invite-invitee@example.com", role="Developer"):
		invite = service.invite_member(self.org["name"], email, role)
		return frappe.db.get_value("Organization Member", invite["name"], "invitation_token")

	def test_valid_acceptance_activates_membership(self):
		token = self._invite_and_get_token()
		frappe.set_user(self.invitee.name)
		result = service.accept_invitation(token)
		self.assertEqual(result["result"], "accepted")

		membership = frappe.db.get_value(
			"Organization Member",
			{"organization": self.org["name"], "user": self.invitee.name},
			["status", "joined_on"],
			as_dict=True,
		)
		self.assertEqual(membership.status, "Active")
		self.assertIsNotNone(membership.joined_on)

	def test_invalid_token_fails_gracefully(self):
		frappe.set_user(self.invitee.name)
		result = service.accept_invitation("not-a-real-token")
		self.assertEqual(result["result"], "invalid")

	def test_expired_token_fails_gracefully(self):
		invite = service.invite_member(self.org["name"], self.invitee.name, "Developer")
		frappe.db.set_value(
			"Organization Member", invite["name"], "invitation_expires_on", add_to_date(now_datetime(), hours=-1)
		)
		token = frappe.db.get_value("Organization Member", invite["name"], "invitation_token")
		frappe.set_user(self.invitee.name)
		result = service.accept_invitation(token)
		self.assertEqual(result["result"], "expired")

	def test_guest_prompted_to_login_for_existing_account(self):
		token = self._invite_and_get_token()
		frappe.set_user("Guest")
		result = service.accept_invitation(token)
		self.assertEqual(result["result"], "login_required")

	def test_guest_prompted_to_signup_for_new_email(self):
		token = self._invite_and_get_token(email="brand-new-invitee@example.com", role="Customer")
		frappe.set_user("Guest")
		result = service.accept_invitation(token)
		self.assertEqual(result["result"], "signup_required")

	def test_identity_mismatch_rejected(self):
		token = self._invite_and_get_token()
		other_user = make_user("invite-someone-else@example.com")
		frappe.set_user(other_user.name)
		result = service.accept_invitation(token)
		self.assertEqual(result["result"], "identity_mismatch")

	def test_reaccepting_same_token_after_acceptance_is_invalid(self):
		# The membership_key DB-level unique constraint (design.md Decision 4)
		# already makes a true "second pending row for the same org+user"
		# unreachable in normal operation; the closest real-world duplicate-
		# acceptance case is replaying an already-consumed token.
		token = self._invite_and_get_token()
		frappe.set_user(self.invitee.name)
		first = service.accept_invitation(token)
		self.assertEqual(first["result"], "accepted")

		second = service.accept_invitation(token)
		self.assertEqual(second["result"], "invalid")
