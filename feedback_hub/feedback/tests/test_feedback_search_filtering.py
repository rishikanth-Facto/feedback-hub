import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization


class TestFeedbackSearchFiltering(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("filter-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Filter Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "Filter Board")
		self.other_board = make_board(self.org["name"], "Filter Other Board")

		self.bug = service.create_feedback(
			self.board["name"], "Login is broken", description="Cannot log in", category="Bug", priority="High"
		)
		self.feature = service.create_feedback(
			self.board["name"],
			"Add export",
			description="Please add CSV export",
			category="Feature Request",
			priority="Low",
		)
		self.other = service.create_feedback(
			self.other_board["name"], "Other board item", description="Something else", category="Other", priority="Medium"
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_filter_by_board(self):
		result = service.list_feedback(board=self.board["name"])
		names = {item["name"] for item in result["feedback"]}
		self.assertEqual(names, {self.bug["name"], self.feature["name"]})

	def test_filter_by_category(self):
		result = service.list_feedback(category="Bug")
		names = {item["name"] for item in result["feedback"]}
		self.assertIn(self.bug["name"], names)
		self.assertNotIn(self.feature["name"], names)

	def test_filter_by_priority(self):
		result = service.list_feedback(priority="High")
		names = {item["name"] for item in result["feedback"]}
		self.assertEqual(names, {self.bug["name"]})

	def test_combined_filters(self):
		result = service.list_feedback(board=self.board["name"], priority="Low")
		names = {item["name"] for item in result["feedback"]}
		self.assertEqual(names, {self.feature["name"]})

	def test_search_matches_title_or_description(self):
		result = service.list_feedback(search="export")
		names = {item["name"] for item in result["feedback"]}
		self.assertEqual(names, {self.feature["name"]})

	def test_sort_by_priority_both_directions(self):
		asc = service.list_feedback(board=self.board["name"], order_by="priority", order_dir="asc")
		desc = service.list_feedback(board=self.board["name"], order_by="priority", order_dir="desc")
		asc_priorities = [item["priority"] for item in asc["feedback"]]
		desc_priorities = [item["priority"] for item in desc["feedback"]]
		self.assertEqual(asc_priorities, sorted(asc_priorities))
		self.assertEqual(desc_priorities, sorted(desc_priorities, reverse=True))

	def test_sort_by_disallowed_field_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.list_feedback(order_by="submitted_by")

	def test_pagination_returns_total_and_slice(self):
		result = service.list_feedback(page=1, page_size=2)
		self.assertEqual(result["total"], 3)
		self.assertEqual(len(result["feedback"]), 2)

		result_page2 = service.list_feedback(page=2, page_size=2)
		self.assertEqual(len(result_page2["feedback"]), 1)

	def test_page_size_zero_returns_everything_unpaginated(self):
		# The pre-existing Kanban board view (fh_kanban.js) relies on this to
		# get every item for its board in one call, exactly as it did before
		# this endpoint gained pagination - page_size <= 0 must never be
		# silently coerced up to the default page size.
		result = service.list_feedback(board=self.board["name"], page_size=0)
		self.assertEqual(len(result["feedback"]), 2)
		self.assertEqual(result["total"], 2)
