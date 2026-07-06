import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.feedback import service
from feedback_hub.feedback.comment import TOMBSTONE_TEXT, _create_comment, _delete_comment
from feedback_hub.feedback.tests.helpers import make_board
from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product import service as product_service
from feedback_hub.product.tests.helpers import add_active_member, make_active_organization, switch_to_organization


class TestFeedbackCommentDeletion(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.admin = make_user("del-admin@example.com")
		cls.author = make_user("del-author@example.com")
		cls.moderator = make_user("del-moderator@example.com")
		cls.product_owner = make_user("del-product-owner@example.com")
		cls.other_product_owner = make_user("del-other-product-owner@example.com")
		cls.developer = make_user("del-developer@example.com")
		cls.customer = make_user("del-customer@example.com")

	def setUp(self):
		self.org = make_active_organization(self.admin.name, "Delete Org " + frappe.generate_hash(length=6))
		for user, role in (
			(self.author, "Customer"),
			(self.moderator, "Moderator"),
			(self.product_owner, "Product Owner"),
			(self.other_product_owner, "Product Owner"),
			(self.developer, "Developer"),
			(self.customer, "Customer"),
		):
			add_active_member(self.org["name"], self.admin.name, user.name, role)
		switch_to_organization(self.admin.name, self.org["name"])

		self.product = product_service.create_product("Delete Product " + frappe.generate_hash(length=6))
		frappe.db.set_value("Product", self.product["name"], "product_owner", self.product_owner.name)
		self.board = product_service.create_board(self.product["name"], "Delete Board", "Public")

		self.other_product = product_service.create_product("Delete Other Product " + frappe.generate_hash(length=6))
		frappe.db.set_value("Product", self.other_product["name"], "product_owner", self.other_product_owner.name)
		self.other_board = product_service.create_board(self.other_product["name"], "Delete Other Board", "Public")

		self.item = service.create_feedback(self.board["name"], "Deletable item", description="please")

		switch_to_organization(self.author.name, self.org["name"])
		self.comment = _create_comment(self.item["name"], "Original comment")
		self.reply = _create_comment(self.item["name"], "A reply", parent_comment=self.comment.name)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _content_of(self, comment_name):
		return frappe.db.get_value("Feedback Comment", comment_name, "comment_text")

	def test_author_deletes_own_comment_tombstoned_replies_visible(self):
		switch_to_organization(self.author.name, self.org["name"])
		result = _delete_comment(self.comment.name)
		self.assertEqual(result["content"], TOMBSTONE_TEXT)

		# Original text is retained in the record itself (only the projection
		# tombstones it) and in its Version history.
		self.assertEqual(self._content_of(self.comment.name), "Original comment")
		self.assertTrue(frappe.db.exists("Feedback Comment", self.reply.name))
		self.assertFalse(frappe.db.get_value("Feedback Comment", self.reply.name, "is_deleted"))

	def test_moderator_deletes_anothers_comment(self):
		switch_to_organization(self.moderator.name, self.org["name"])
		_delete_comment(self.comment.name)
		self.assertTrue(frappe.db.get_value("Feedback Comment", self.comment.name, "is_deleted"))

	def test_product_owner_deletes_within_owned_product_only(self):
		switch_to_organization(self.product_owner.name, self.org["name"])
		_delete_comment(self.comment.name)
		self.assertTrue(frappe.db.get_value("Feedback Comment", self.comment.name, "is_deleted"))

		other_item = service.create_feedback(self.other_board["name"], "Other item", description="please")
		switch_to_organization(self.author.name, self.org["name"])
		other_comment = _create_comment(other_item["name"], "Other comment")

		switch_to_organization(self.product_owner.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_delete_comment(other_comment.name)

	def test_organization_admin_deletes_any_comment(self):
		switch_to_organization(self.admin.name, self.org["name"])
		_delete_comment(self.comment.name)
		self.assertTrue(frappe.db.get_value("Feedback Comment", self.comment.name, "is_deleted"))

	def test_customer_and_developer_cannot_delete_others_comments(self):
		switch_to_organization(self.customer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_delete_comment(self.comment.name)

		switch_to_organization(self.developer.name, self.org["name"])
		with self.assertRaises(frappe.PermissionError):
			_delete_comment(self.comment.name)
