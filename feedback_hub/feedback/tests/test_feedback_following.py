import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.follow import _toggle_follow
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackFollowing(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("follow-owner@example.com")
		cls.customer = make_user("follow-customer@example.com")
		cls.outsider = make_user("follow-outsider@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Follow Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.customer.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Follow Board")
		self.private_board = make_board(self.org["name"], "Follow Private Board", visibility="Private")
		self.item = service.create_feedback(self.board["name"], "Followable item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_follow_unfollow_toggle_and_follower_count(self):
		result = _toggle_follow(self.item["name"])
		self.assertTrue(result["following"])
		self.assertEqual(result["follower_count"], 1)

		result = _toggle_follow(self.item["name"])
		self.assertFalse(result["following"])
		self.assertEqual(result["follower_count"], 0)

	def test_duplicate_follow_prevented(self):
		doc = frappe.get_doc({"doctype": "Feedback Follower", "feedback": self.item["name"], "user": self.owner.name})
		doc.insert()
		duplicate = frappe.get_doc({"doctype": "Feedback Follower", "feedback": self.item["name"], "user": self.owner.name})
		with self.assertRaises(frappe.DuplicateEntryError):
			duplicate.insert()

	def test_refollow_after_unfollow_creates_fresh_row(self):
		_toggle_follow(self.item["name"])
		_toggle_follow(self.item["name"])
		result = _toggle_follow(self.item["name"])
		self.assertTrue(result["following"])
		self.assertEqual(frappe.db.count("Feedback Follower", {"feedback": self.item["name"], "user": self.owner.name}), 1)

	def test_following_deleted_feedback_rejected(self):
		item = service.create_feedback(self.board["name"], "Will be deleted", description="please")
		frappe.delete_doc("Feedback", item["name"], ignore_permissions=True)
		with self.assertRaises(frappe.DoesNotExistError):
			_toggle_follow(item["name"])

	def test_unauthenticated_caller_rejected(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			_toggle_follow(self.item["name"])

	def test_board_invisible_feedback_rejected(self):
		private_item = service.create_feedback(self.private_board["name"], "Private item", description="please")
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_toggle_follow(private_item["name"])

	def test_organization_isolation(self):
		_toggle_follow(self.item["name"])

		other_owner = make_user("follow-other-owner@example.com")
		other_org = make_active_organization(other_owner.name, "Follow Other Org " + frappe.generate_hash(length=6))
		add_active_member(other_org["name"], other_owner.name, self.owner.name, "Customer")
		switch_to_organization(self.owner.name, other_org["name"])

		visible = frappe.get_list("Feedback Follower", filters={"feedback": self.item["name"]})
		self.assertEqual(len(visible), 0)
