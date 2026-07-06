import frappe
from frappe import _
from frappe.model.document import Document

from feedback_hub.product.utils import generate_unique_slug


class Product(Document):
	def autoname(self):
		# Same controller-autoname pattern as Organization (design.md Decision 7) -
		# Frappe's built-in autoname: "hash" has no prefix support.
		self.name = "PRD-" + frappe.generate_hash(length=8)

	def before_insert(self):
		if not self.slug:
			self.slug = generate_unique_slug(self.product_name, "organization", self.organization)
		if not self.product_owner:
			self.product_owner = frappe.session.user
		if not self.status:
			self.status = "Active"

	def validate(self):
		if frappe.db.exists(
			"Product",
			{"product_name": self.product_name, "organization": self.organization, "name": ["!=", self.name]},
		):
			frappe.throw(
				_("A product with this name already exists in this organization."), frappe.DuplicateEntryError
			)

	def on_trash(self):
		boards = frappe.db.count("Board", {"product": self.name})
		if boards and not frappe.flags.get("force_delete_product"):
			frappe.throw(
				_(
					"Cannot delete product {0}: it still has {1} board(s). "
					"Remove them first or use force delete."
				).format(self.product_name, boards),
				frappe.LinkExistsError,
			)
		if frappe.flags.get("force_delete_product"):
			for board in frappe.get_all("Board", filters={"product": self.name}, pluck="name"):
				frappe.delete_doc("Board", board, ignore_permissions=True, force=True)
