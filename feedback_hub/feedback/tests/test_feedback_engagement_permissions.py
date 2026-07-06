import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import _create_comment, _delete_comment
from feedback_hub.feedback.follow import _toggle_follow
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.feedback.vote import _toggle_vote
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization

ENGAGING_ROLES = ("Customer", "Moderator", "Product Owner", "Organization Admin", "Developer")


class TestFeedbackEngagementPermissions(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("ep-admin@example.com")
		cls.users = {role: make_user(f"ep-{role.lower().replace(' ', '-')}@example.com") for role in ENGAGING_ROLES}

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Engagement Perm Org " + frappe.generate_hash(length=6))
		for role, user in self.users.items():
			if role == "Organization Admin":
				continue
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])
		self.board = make_board(self.org["name"], "Engagement Perm Board")
		self.item = service.create_feedback(self.board["name"], "Engagement item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_every_role_with_board_access_can_vote_comment_reply_follow(self):
		for role, user in self.users.items():
			if role == "Organization Admin":
				switch_to_organization(self.admin.name, self.org["name"])
			else:
				switch_to_organization(user.name, self.org["name"])

			vote_result = _toggle_vote(self.item["name"])
			self.assertTrue(vote_result["voted"], f"{role} should be able to vote")

			root = _create_comment(self.item["name"], f"{role} comment")
			self.assertIsNotNone(root.name, f"{role} should be able to comment")

			reply = _create_comment(self.item["name"], f"{role} reply", parent_comment=root.name)
			self.assertEqual(reply.parent_comment, root.name, f"{role} should be able to reply")

			follow_result = _toggle_follow(self.item["name"])
			self.assertTrue(follow_result["following"], f"{role} should be able to follow")

	def test_comment_delete_matrix(self):
		switch_to_organization(self.users["Customer"].name, self.org["name"])
		comment = _create_comment(self.item["name"], "Customer's comment")

		# Author may delete their own.
		_delete_comment(comment.name)
		self.assertTrue(frappe.db.get_value("Feedback Comment", comment.name, "is_deleted"))

		other_comment = _create_comment(self.item["name"], "Another comment")

		switch_to_organization(self.users["Developer"].name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_delete_comment(other_comment.name)

		switch_to_organization(self.users["Moderator"].name, self.org["name"])
		_delete_comment(other_comment.name)
		self.assertTrue(frappe.db.get_value("Feedback Comment", other_comment.name, "is_deleted"))

	def test_cross_organization_access_rejected(self):
		outsider = make_user("ep-outsider@example.com")
		other_org = make_active_organization(outsider.name, "Engagement Other Org " + frappe.generate_hash(length=6))
		switch_to_organization(outsider.name, other_org["name"])

		with self.assertRaises(frappe.PermissionError):
			_toggle_vote(self.item["name"])
		with self.assertRaises(frappe.PermissionError):
			_create_comment(self.item["name"], "Sneaky comment")
		with self.assertRaises(frappe.PermissionError):
			_toggle_follow(self.item["name"])

	def test_membership_in_inactive_organization_does_not_grant_access(self):
		multi_org_user = make_user("ep-multi-org@example.com")
		add_active_member(self.org["name"], self.admin.name, multi_org_user.name, "Customer")

		other_owner = make_user("ep-other-owner@example.com")
		other_org = make_active_organization(other_owner.name, "Engagement Multi Org " + frappe.generate_hash(length=6))
		add_active_member(other_org["name"], other_owner.name, multi_org_user.name, "Customer")

		# multi_org_user IS an active member of self.org, but other_org is
		# their currently active organization - membership alone is not enough.
		switch_to_organization(multi_org_user.name, other_org["name"])
		with self.assertRaises(frappe.PermissionError):
			_toggle_vote(self.item["name"])
