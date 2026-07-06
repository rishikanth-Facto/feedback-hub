import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization


class TestFeedbackVoteDoctype(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("fv-doctype-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "FV Doctype Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "FV Doctype Board")
		self.item = service.create_feedback(self.board["name"], "Votable", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_unique_constraint_survives_soft_delete(self):
		vote = frappe.get_doc({"doctype": "Feedback Vote", "feedback": self.item["name"], "user": self.owner.name})
		vote.insert()
		vote.is_deleted = 1
		vote.save(ignore_permissions=True)

		duplicate = frappe.get_doc({"doctype": "Feedback Vote", "feedback": self.item["name"], "user": self.owner.name})
		with self.assertRaises(frappe.DuplicateEntryError):
			duplicate.insert()

	def test_on_update_adjusts_vote_count_on_toggle_transitions(self):
		vote = frappe.get_doc({"doctype": "Feedback Vote", "feedback": self.item["name"], "user": self.owner.name})
		vote.insert()
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 1)

		vote.is_deleted = 1
		vote.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 0)

		vote.is_deleted = 0
		vote.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 1)

	def test_after_insert_fires_only_on_genuine_first_insert(self):
		vote = frappe.get_doc({"doctype": "Feedback Vote", "feedback": self.item["name"], "user": self.owner.name})
		vote.insert()
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 1)

		# Re-saving with is_deleted unchanged must not double-count - on_update
		# only reacts to an actual before/after transition.
		vote.reload()
		vote.save(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Feedback", self.item["name"], "vote_count"), 1)
