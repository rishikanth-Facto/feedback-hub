import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.feedback.vote import _toggle_vote
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackVotingToggle(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("vt-owner@example.com")
		cls.customer = make_user("vt-customer@example.com")
		cls.outsider = make_user("vt-outsider@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Vote Toggle Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.customer.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Vote Toggle Board")
		self.private_board = make_board(self.org["name"], "Vote Toggle Private Board", visibility="Private")
		self.item = service.create_feedback(self.board["name"], "Votable item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_first_vote_unvote_revote_sequence(self):
		result = _toggle_vote(self.item["name"])
		self.assertTrue(result["voted"])
		self.assertEqual(result["total_votes"], 1)

		result = _toggle_vote(self.item["name"])
		self.assertFalse(result["voted"])
		self.assertEqual(result["total_votes"], 0)

		result = _toggle_vote(self.item["name"])
		self.assertTrue(result["voted"])
		self.assertEqual(result["total_votes"], 1)

		# Re-voting reuses the same row rather than inserting a second one.
		self.assertEqual(frappe.db.count("Feedback Vote", {"feedback": self.item["name"], "user": self.owner.name}), 1)

	def test_vote_on_anonymous_feedback_succeeds(self):
		anon_item = service.create_feedback(self.board["name"], "Anon item", description="please", is_anonymous=True)
		result = _toggle_vote(anon_item["name"])
		self.assertTrue(result["voted"])
		self.assertEqual(result["total_votes"], 1)

	def test_voting_on_archived_product_feedback_rejected(self):
		# Archive the product backing this item's board.
		frappe.db.set_value("Product", frappe.db.get_value("Board", self.board["name"], "product"), "status", "Archived")
		with self.assertRaises(frappe.ValidationError):
			_toggle_vote(self.item["name"])
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 0)

	def test_voting_on_deleted_feedback_rejected(self):
		item = service.create_feedback(self.board["name"], "Will be deleted", description="please")
		frappe.delete_doc("Feedback", item["name"], ignore_permissions=True)
		with self.assertRaises(frappe.DoesNotExistError):
			_toggle_vote(item["name"])

	def test_unauthenticated_caller_rejected(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			_toggle_vote(self.item["name"])

	def test_non_member_rejected(self):
		frappe.set_user(self.outsider.name)
		with self.assertRaises(frappe.PermissionError):
			_toggle_vote(self.item["name"])

	def test_board_invisible_feedback_rejected(self):
		private_item = service.create_feedback(self.private_board["name"], "Private item", description="please")
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_toggle_vote(private_item["name"])

	def test_organization_isolation_on_vote_visibility(self):
		_toggle_vote(self.item["name"])

		other_owner = make_user("vt-other-owner@example.com")
		other_org = make_active_organization(other_owner.name, "Vote Toggle Other Org " + frappe.generate_hash(length=6))
		add_active_member(other_org["name"], other_owner.name, self.owner.name, "Customer")
		switch_to_organization(self.owner.name, other_org["name"])

		visible = frappe.get_list("Feedback Vote", filters={"feedback": self.item["name"]})
		self.assertEqual(len(visible), 0)
