import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackRoleVisibility(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("vis-admin@example.com")
		cls.moderator = make_user("vis-moderator@example.com")
		cls.customer = make_user("vis-customer@example.com")
		cls.other_customer = make_user("vis-other-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Visibility Org " + frappe.generate_hash(length=6))
		for user, role in (
			(self.moderator, "Moderator"),
			(self.customer, "Customer"),
			(self.other_customer, "Customer"),
		):
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Visibility Board")

		switch_to_organization(self.customer.name, self.org["name"])
		self.item = service.create_feedback(self.board["name"], "Visibility item", description="please")
		service.add_attachment(self.item["name"], "notes.txt", b"hello")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_submitter_sees_own_attachments(self):
		data = service.get_feedback(self.item["name"])
		self.assertEqual(len(data["attachments"]), 1)

	def test_other_customer_sees_attachments_on_public_board(self):
		# Revised: a screenshot attached to a public bug report should be
		# visible to whoever can already read that report, not only its
		# author/Moderator/Product Owner/Organization Admin.
		switch_to_organization(self.other_customer.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertEqual(len(data["attachments"]), 1)

	def test_developer_cannot_see_attachments_on_private_board(self):
		# Developer already has org-wide read access including Private boards
		# (unchanged, pre-existing behavior) - the public-board exception only
		# extends to Public boards, so a non-owner/non-elevated viewer of a
		# Private item still gets no attachments.
		switch_to_organization(self.admin.name, self.org["name"])
		developer = make_user("vis-developer@example.com")
		add_active_member(self.org["name"], self.admin.name, developer.name, "Developer")
		private_board = make_board(self.org["name"], "Private Visibility Board", visibility="Private")

		# Admin (not self.customer, who has no read access to a Private board
		# at all) submits, so the Developer viewer below is a genuine
		# non-owner/non-elevated case.
		private_item = service.create_feedback(private_board["name"], "Private visibility item", description="please")
		service.add_attachment(private_item["name"], "secret.txt", b"hush")

		switch_to_organization(developer.name, self.org["name"])
		data = service.get_feedback(private_item["name"])
		self.assertEqual(data["attachments"], [])

	def test_moderator_sees_attachments_and_activity_history(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		service.update_feedback(self.item["name"], title="Moderator retitled")
		data = service.get_feedback(self.item["name"])
		self.assertEqual(len(data["attachments"]), 1)
		self.assertTrue(len(data["activity_history"]) >= 1)

	def test_submitter_does_not_see_moderation_activity_history(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		service.update_feedback(self.item["name"], title="Moderator retitled")

		switch_to_organization(self.customer.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertEqual(data["activity_history"], [])

	def test_other_customer_does_not_see_activity_history(self):
		switch_to_organization(self.other_customer.name, self.org["name"])
		data = service.get_feedback(self.item["name"])
		self.assertEqual(data["activity_history"], [])


class TestDeletedFeedbackRecovery(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("del-admin@example.com")
		cls.customer = make_user("del-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Deleted Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.admin.name, self.customer.name, "Customer")
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Deleted Board")
		self.item = service.create_feedback(self.board["name"], "About to be deleted", description="please")
		service.delete_feedback(self.item["name"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_org_admin_can_view_deleted_feedback(self):
		deleted = service.list_deleted_feedback(self.org["name"])
		names = {row["name"] for row in deleted}
		self.assertIn(self.item["name"], names)

	def test_non_admin_cannot_view_deleted_feedback(self):
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.list_deleted_feedback(self.org["name"])
