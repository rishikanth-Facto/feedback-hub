import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import comment as comment_module
from feedback_hub.feedback import follow as follow_module
from feedback_hub.feedback import service
from feedback_hub.feedback import vote as vote_module
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization, switch_to_organization


class TestFeedbackEngagementSecurity(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("sec-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Security Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "Security Board")
		self.item = service.create_feedback(self.board["name"], "Security item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_invalid_feedback_id_returns_not_found_across_endpoints(self):
		bogus = "FDB-doesnotexist"
		vote_response = vote_module.toggle_vote(feedback_id=bogus)
		self.assertFalse(vote_response["success"])

		comment_response = comment_module.create_comment(feedback=bogus, content="hi")
		self.assertFalse(comment_response["success"])

		list_response = comment_module.list_comments(feedback=bogus)
		self.assertFalse(list_response["success"])

		follow_response = follow_module.toggle_follow(feedback=bogus)
		self.assertFalse(follow_response["success"])

	def test_invalid_comment_id_returns_not_found(self):
		bogus = "FDC-doesnotexist"
		update_response = comment_module.update_comment(comment=bogus, content="hi")
		self.assertFalse(update_response["success"])

		delete_response = comment_module.delete_comment(comment=bogus)
		self.assertFalse(delete_response["success"])

	def test_unauthenticated_calls_return_auth_error_across_endpoints(self):
		frappe.set_user("Guest")
		self.assertFalse(vote_module.toggle_vote(feedback_id=self.item["name"])["success"])
		self.assertFalse(comment_module.create_comment(feedback=self.item["name"], content="hi")["success"])
		self.assertFalse(follow_module.toggle_follow(feedback=self.item["name"])["success"])

	def test_consistent_envelope_shape_on_error_paths(self):
		frappe.set_user("Guest")
		response = vote_module.toggle_vote(feedback_id=self.item["name"])
		self.assertIn("success", response)
		self.assertIn("message", response)
		self.assertIn("data", response)
		self.assertFalse(response["success"])
