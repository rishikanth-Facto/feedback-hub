import frappe
from frappe import _
from frappe.model.document import Document


class FeedbackComment(Document):
	def autoname(self):
		self.name = "FDC-" + frappe.generate_hash(length=8)

	def before_insert(self):
		if not self.commented_by:
			self.commented_by = frappe.session.user
		self.organization = frappe.db.get_value("Feedback", self.feedback, "organization")

	def validate(self):
		if not self.comment_text or not self.comment_text.strip():
			frappe.throw(_("Comment text is required."), frappe.ValidationError)
		if self.parent_comment:
			parent_feedback = frappe.db.get_value("Feedback Comment", self.parent_comment, "feedback")
			if not parent_feedback:
				frappe.throw(_("Parent comment does not exist."), frappe.DoesNotExistError)
			if parent_feedback != self.feedback:
				frappe.throw(_("Parent comment must belong to the same feedback item."), frappe.ValidationError)
