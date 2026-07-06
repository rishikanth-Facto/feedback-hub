import frappe
from frappe import _
from frappe.model.document import Document


class FeedbackVote(Document):
	def autoname(self):
		self.name = "FDV-" + frappe.generate_hash(length=8)

	def before_insert(self):
		self.vote_key = f"{self.feedback}:{self.user}"
		self.organization = frappe.db.get_value("Feedback", self.feedback, "organization")

	def validate(self):
		# Friendly duplicate-vote check alongside the DB-level unique vote_key
		# (design.md Decision 5, same dual-guard shape as Organization
		# Member.membership_key) - the service layer's toggle_vote already
		# checks for an existing vote before inserting, so this only guards
		# a genuine concurrent-request race. Unchanged by soft delete (Module 5
		# design.md Decision 3): the unique vote_key must hold across the full
		# toggle history, not just currently-active votes.
		if frappe.db.exists("Feedback Vote", {"feedback": self.feedback, "user": self.user, "name": ["!=", self.name or ""]}):
			frappe.throw(_("You have already voted for this feedback item."), frappe.DuplicateEntryError)

	def after_insert(self):
		# Atomic increment, not a read-then-write, so concurrent votes can't
		# race each other into an undercount (design.md Decision 4). Only
		# fires on a genuine first-ever vote, always inserted with
		# is_deleted=0 by toggle_vote - on_update below handles every later
		# toggle transition (Module 5 design.md Decision 3).
		frappe.db.sql("update `tabFeedback` set vote_count = vote_count + 1 where name = %s", self.feedback)

	def on_update(self):
		# Toggling is_deleted on the same row (re-vote/un-vote) never goes
		# through after_insert/on_trash again - this is the only place a
		# toggle's vote_count effect is applied (Module 5 design.md Decision 3).
		# get_doc_before_save() is None on the initial insert (already handled
		# by after_insert above), so only a real transition on an existing row
		# is counted here.
		before = self.get_doc_before_save()
		if not before:
			return
		if not before.is_deleted and self.is_deleted:
			frappe.db.sql(
				"update `tabFeedback` set vote_count = vote_count - 1 where name = %s and vote_count > 0", self.feedback
			)
		elif before.is_deleted and not self.is_deleted:
			frappe.db.sql("update `tabFeedback` set vote_count = vote_count + 1 where name = %s", self.feedback)

	def on_trash(self):
		# Defensive fallback for a direct hard delete (e.g. an Organization
		# Admin deleting a vote row from Desk) - toggle_vote itself never
		# hard-deletes a Feedback Vote (Module 5 design.md Decision 3).
		if self.is_deleted:
			return
		frappe.db.sql(
			"update `tabFeedback` set vote_count = vote_count - 1 where name = %s and vote_count > 0", self.feedback
		)
