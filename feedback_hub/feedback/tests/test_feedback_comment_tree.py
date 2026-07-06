import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import _create_comment, _list_comments
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product.tests.helpers import make_active_organization


class TestFeedbackCommentTree(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("tree-owner@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Tree Org " + frappe.generate_hash(length=6))
		self.board = make_board(self.org["name"], "Tree Board")
		self.item = service.create_feedback(self.board["name"], "Tree item", description="please")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _find(self, nodes, name):
		for node in nodes:
			if node["name"] == name:
				return node
			found = self._find(node["replies"], name)
			if found:
				return found
		return None

	def test_tree_nesting_across_three_levels(self):
		root = _create_comment(self.item["name"], "Root")
		reply1 = _create_comment(self.item["name"], "Reply 1", parent_comment=root.name)
		reply2 = _create_comment(self.item["name"], "Reply 2", parent_comment=root.name)
		nested = _create_comment(self.item["name"], "Nested reply", parent_comment=reply1.name)

		data = _list_comments(self.item["name"])
		self.assertEqual(len(data["comments"]), 1)

		root_node = data["comments"][0]
		self.assertEqual(root_node["name"], root.name)
		reply_names = {r["name"] for r in root_node["replies"]}
		self.assertEqual(reply_names, {reply1.name, reply2.name})

		reply1_node = self._find(data["comments"], reply1.name)
		self.assertEqual([r["name"] for r in reply1_node["replies"]], [nested.name])

	def test_reply_count_accuracy(self):
		root = _create_comment(self.item["name"], "Root")
		_create_comment(self.item["name"], "R1", parent_comment=root.name)
		_create_comment(self.item["name"], "R2", parent_comment=root.name)
		_create_comment(self.item["name"], "R3", parent_comment=root.name)

		data = _list_comments(self.item["name"])
		self.assertEqual(data["comments"][0]["reply_count"], 3)

	def test_pagination_over_root_comments(self):
		for i in range(5):
			_create_comment(self.item["name"], f"Root {i}")

		page1 = _list_comments(self.item["name"], page=1, page_size=2)
		self.assertEqual(len(page1["comments"]), 2)
		self.assertEqual(page1["total"], 5)

		page3 = _list_comments(self.item["name"], page=3, page_size=2)
		self.assertEqual(len(page3["comments"]), 1)

	def test_edited_attachments_and_author_fields_present(self):
		root = _create_comment(self.item["name"], "Root")
		data = _list_comments(self.item["name"])
		node = data["comments"][0]
		self.assertEqual(node["author"], self.owner.name)
		self.assertFalse(node["edited"])
		self.assertEqual(node["attachments"], [])
		self.assertIn("creation", node)
