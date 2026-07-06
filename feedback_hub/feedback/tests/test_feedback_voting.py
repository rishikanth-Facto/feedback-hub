import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackVoting(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("vote-owner@example.com")
		cls.voter_a = make_user("vote-voter-a@example.com")
		cls.voter_b = make_user("vote-voter-b@example.com")
		cls.customer = make_user("vote-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Vote Test Org " + frappe.generate_hash(length=6))
		for user, role in ((self.voter_a, "Developer"), (self.voter_b, "Developer"), (self.customer, "Customer")):
			add_active_member(self.org["name"], self.owner.name, user.name, role)
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Vote Board")
		self.private_board = make_board(self.org["name"], "Vote Private Board", visibility="Private")
		self.item = service.create_feedback(self.board["name"], "Votable item", description="Please add this.")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_first_vote_increments_count(self):
		result = service.toggle_vote(self.item["name"])
		self.assertTrue(result["voted"])
		self.assertEqual(result["vote_count"], 1)

	def test_second_toggle_removes_vote(self):
		service.toggle_vote(self.item["name"])
		result = service.toggle_vote(self.item["name"])
		self.assertFalse(result["voted"])
		self.assertEqual(result["vote_count"], 0)

	def test_three_distinct_voters_produce_count_of_three(self):
		service.toggle_vote(self.item["name"])
		switch_to_organization(self.voter_a.name, self.org["name"])
		service.toggle_vote(self.item["name"])
		switch_to_organization(self.voter_b.name, self.org["name"])
		result = service.toggle_vote(self.item["name"])
		self.assertEqual(result["vote_count"], 3)

	def test_vote_count_after_a_removal(self):
		service.toggle_vote(self.item["name"])
		switch_to_organization(self.voter_a.name, self.org["name"])
		service.toggle_vote(self.item["name"])
		switch_to_organization(self.voter_b.name, self.org["name"])
		service.toggle_vote(self.item["name"])

		switch_to_organization(self.voter_a.name, self.org["name"])
		result = service.toggle_vote(self.item["name"])
		self.assertEqual(result["vote_count"], 2)

	def test_voting_without_board_read_access_rejected(self):
		private_item = service.create_feedback(self.private_board["name"], "Private item", description="Details.")
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.toggle_vote(private_item["name"])
