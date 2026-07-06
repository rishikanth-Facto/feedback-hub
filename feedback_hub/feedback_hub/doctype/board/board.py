import frappe
from frappe import _
from frappe.model.document import Document

from feedback_hub.product.utils import BOARD_VISIBILITIES, generate_unique_slug


class Board(Document):
	def autoname(self):
		self.name = "BRD-" + frappe.generate_hash(length=8)

	def before_insert(self):
		if not self.slug:
			self.slug = generate_unique_slug(self.board_name, "product", self.product, doctype="Board")

	def validate(self):
		if frappe.db.exists(
			"Board", {"board_name": self.board_name, "product": self.product, "name": ["!=", self.name]}
		):
			frappe.throw(_("A board with this name already exists in this product."), frappe.DuplicateEntryError)
		if self.visibility not in BOARD_VISIBILITIES:
			frappe.throw(_("Invalid visibility."), frappe.ValidationError)
