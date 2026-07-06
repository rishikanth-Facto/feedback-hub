import frappe
from frappe.tests.utils import FrappeTestCase

from feedback_hub.organization.tests.helpers import make_user
from feedback_hub.product import service
from feedback_hub.product.tests.helpers import make_active_organization


class TestBoard(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.owner = make_user("board-owner-user@example.com")

	def setUp(self):
		self.org = make_active_organization(self.owner.name, "Board Test Org " + frappe.generate_hash(length=6))
		self.product = service.create_product("Board Test Product " + frappe.generate_hash(length=6))

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_create_board_success(self):
		board = service.create_board(self.product["name"], "Feature Requests", "Public", description="hi")
		self.assertEqual(board["board_name"], "Feature Requests")
		self.assertEqual(board["slug"], "feature-requests")
		self.assertEqual(board["visibility"], "Public")
		self.assertEqual(board["product"], self.product["name"])

	def test_creation_on_archived_product_rejected(self):
		service.update_product(self.product["name"], status="Archived")
		with self.assertRaises(frappe.ValidationError):
			service.create_board(self.product["name"], "Blocked Board", "Public")

	def test_editing_existing_board_after_product_archived_not_blocked(self):
		board = service.create_board(self.product["name"], "Survives Archive", "Public")
		service.update_product(self.product["name"], status="Archived")
		updated = service.update_board(board["name"], description="still editable")
		self.assertEqual(updated["description"], "still editable")

	def test_missing_visibility_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_board(self.product["name"], "No Visibility", None)

	def test_invalid_visibility_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			service.create_board(self.product["name"], "Bad Visibility", "SuperSecret")

	def test_valid_visibility_accepted(self):
		board = service.create_board(self.product["name"], "Internal Only", "Internal")
		self.assertEqual(board["visibility"], "Internal")

	def test_duplicate_name_within_same_product_rejected(self):
		service.create_board(self.product["name"], "Duplicate Board", "Public")
		with self.assertRaises(frappe.DuplicateEntryError):
			service.create_board(self.product["name"], "Duplicate Board", "Private")

	def test_same_name_allowed_under_different_product(self):
		service.create_board(self.product["name"], "Shared Board Name", "Public")
		other_product = service.create_product("Other Product " + frappe.generate_hash(length=6))
		board = service.create_board(other_product["name"], "Shared Board Name", "Public")
		self.assertEqual(board["product"], other_product["name"])

	def test_slug_collision_within_product_gets_numeric_suffix(self):
		b1 = service.create_board(self.product["name"], "Collide Board", "Public")
		b2 = service.create_board(self.product["name"], "Collide  Board!!", "Public")
		self.assertNotEqual(b1["slug"], b2["slug"])
		self.assertTrue(b2["slug"].startswith("collide-board"))

	def test_update_board(self):
		board = service.create_board(self.product["name"], "Updatable Board", "Public")
		updated = service.update_board(board["name"], visibility="Private")
		self.assertEqual(updated["visibility"], "Private")

	def test_update_to_invalid_visibility_rejected(self):
		board = service.create_board(self.product["name"], "Invalid Update Board", "Public")
		with self.assertRaises(frappe.ValidationError):
			service.update_board(board["name"], visibility="SuperSecret")

	def test_delete_has_no_guard(self):
		board = service.create_board(self.product["name"], "Deletable Board", "Public")
		result = service.delete_board(board["name"])
		self.assertTrue(result["deleted"])
		self.assertFalse(frappe.db.exists("Board", board["name"]))
