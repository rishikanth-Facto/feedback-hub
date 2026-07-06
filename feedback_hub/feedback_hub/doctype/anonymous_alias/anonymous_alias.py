import frappe
from frappe import _
from frappe.model.document import Document


class AnonymousAlias(Document):
	def validate(self):
		existing = frappe.db.exists(
			"Anonymous Alias",
			{"user": self.user, "organization": self.organization, "name": ["!=", self.name or ""]},
		)
		if existing:
			frappe.throw(_("An alias already exists for this user in this organization."), frappe.DuplicateEntryError)
