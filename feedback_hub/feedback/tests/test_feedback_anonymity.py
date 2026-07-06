import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackAnonymity(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("anon-admin@example.com")
		cls.submitter = make_user("anon-submitter@example.com")
		cls.moderator = make_user("anon-moderator@example.com")
		cls.other_customer = make_user("anon-other-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Anon Org " + frappe.generate_hash(length=6))
		for user, role in (
			(self.submitter, "Customer"),
			(self.moderator, "Moderator"),
			(self.other_customer, "Customer"),
		):
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Anon Board")

		switch_to_organization(self.submitter.name, self.org["name"])
		self.item = service.create_feedback(self.board["name"], "Anon item", description="please", is_anonymous=1)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_submitter_sees_own_identity(self):
		data = service.get_feedback(self.item["name"])
		self.assertEqual(data["submitted_by"], self.submitter.name)
		self.assertEqual(data["reporter"], self.submitter.name)

	def test_other_customer_cannot_see_identity(self):
		switch_to_organization(self.other_customer.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertIsNone(data["submitted_by"])

	def test_moderator_cannot_see_identity(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertIsNone(data["submitted_by"])

	def test_moderator_sees_persistent_alias_not_real_identity(self):
		# Moderator/Product Owner get a stable per-organization alias instead
		# of the real identity (spec: feedback-anonymity "Persistent Alias") -
		# submitted_by stays redacted, but reporter is a non-None stand-in.
		switch_to_organization(self.moderator.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertIsNone(data["submitted_by"])
		self.assertIsNotNone(data["reporter"])
		self.assertNotEqual(data["reporter"], self.submitter.name)

	def test_alias_is_reused_across_submissions_in_same_organization(self):
		switch_to_organization(self.submitter.name, self.org["name"])
		second_item = service.create_feedback(self.board["name"], "Second anon item", description="please", is_anonymous=1)

		switch_to_organization(self.moderator.name, self.org["name"])
		first_alias = service.get_feedback(self.item["name"])["reporter"]
		second_alias = service.get_feedback(second_item["name"])["reporter"]
		self.assertEqual(first_alias, second_alias)

	def test_other_customer_sees_alias_not_real_identity(self):
		# Revised: a fellow Customer benefits from telling anonymous
		# participants apart in a discussion thread, same as Moderator/
		# Product Owner - only the real identity is sensitive.
		switch_to_organization(self.other_customer.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertIsNone(data["submitted_by"])
		self.assertIsNotNone(data["reporter"])
		self.assertNotEqual(data["reporter"], self.submitter.name)

	def test_organization_admin_sees_identity(self):
		switch_to_organization(self.admin.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertEqual(data["submitted_by"], self.submitter.name)
		self.assertEqual(data["reporter"], self.submitter.name)

	def test_real_creator_is_preserved_internally_regardless_of_redaction(self):
		switch_to_organization(self.other_customer.name, self.org["name"])
		redacted = service.get_feedback(self.item["name"])
		self.assertIsNone(redacted["submitted_by"])

		raw_submitted_by = frappe.db.get_value("Feedback", self.item["name"], "submitted_by")
		self.assertEqual(raw_submitted_by, self.submitter.name)

	def test_list_redacts_identity_for_non_owner(self):
		switch_to_organization(self.other_customer.name, self.org["name"])
		result = service.list_feedback(board=self.board["name"])
		item = next(f for f in result["feedback"] if f["name"] == self.item["name"])
		self.assertIsNone(item["submitted_by"])
