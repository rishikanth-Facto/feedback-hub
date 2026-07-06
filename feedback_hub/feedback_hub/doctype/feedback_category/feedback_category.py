import frappe
from frappe import _
from frappe.model.document import Document


class FeedbackCategory(Document):
	def validate(self):
		self._check_duplicate_name()

	def _check_duplicate_name(self):
		existing = frappe.db.exists(
			"Feedback Category",
			{"category_name": ["like", self.category_name], "name": ["!=", self.name or ""]},
		)
		if existing:
			frappe.throw(_("A category with this name already exists."), frappe.DuplicateEntryError)
