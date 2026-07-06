import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackCommenting(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("comment-owner@example.com")
		cls.customer = make_user("comment-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Comment Test Org " + frappe.generate_hash(length=6))
		add_active_member(self.org["name"], self.owner.name, self.customer.name, "Customer")
		switch_to_organization(self.owner.name, self.org["name"])
		self.board = make_board(self.org["name"], "Comment Board")
		self.private_board = make_board(self.org["name"], "Comment Private Board", visibility="Private")
		self.item = service.create_feedback(self.board["name"], "Commentable item", description="Please add this.")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_comment_creation_success(self):
		comment = service.add_comment(self.item["name"], "Great idea!")
		self.assertEqual(comment["comment_text"], "Great idea!")
		self.assertEqual(comment["commented_by"], self.owner.name)

	def test_empty_comment_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.add_comment(self.item["name"], "   ")

	def test_comments_returned_oldest_first(self):
		service.add_comment(self.item["name"], "First")
		service.add_comment(self.item["name"], "Second")
		data = service.get_feedback(self.item["name"])
		texts = [c["comment_text"] for c in data["comments"]]
		self.assertEqual(texts, ["First", "Second"])

	def test_commenting_without_board_read_access_rejected(self):
		private_item = service.create_feedback(self.private_board["name"], "Private item", description="Details.")
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			service.add_comment(private_item["name"], "Sneaky comment")
