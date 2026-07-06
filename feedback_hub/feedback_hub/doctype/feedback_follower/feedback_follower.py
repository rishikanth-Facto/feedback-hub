import frappe
from frappe import _
from frappe.model.document import Document


class FeedbackFollower(Document):
	def autoname(self):
		self.name = "FDF-" + frappe.generate_hash(length=8)

	def before_insert(self):
		self.follow_key = f"{self.feedback}:{self.user}"
		self.organization = frappe.db.get_value("Feedback", self.feedback, "organization")

	def validate(self):
		# Same dual-guard shape as Feedback Vote.vote_key - the service layer's
		# toggle_follow already checks for an existing follow before inserting,
		# this only guards a genuine concurrent-request race.
		if frappe.db.exists("Feedback Follower", {"feedback": self.feedback, "user": self.user, "name": ["!=", self.name or ""]}):
			frappe.throw(_("You are already following this feedback item."), frappe.DuplicateEntryError)
