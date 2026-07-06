import frappe
from frappe import _
from frappe.model.document import Document

from feedback_hub.feedback.anonymity import get_or_create_alias

FEEDBACK_STATUSES = ["New", "Under Review", "Approved", "Rejected", "Planned", "In Progress", "Released", "Closed"]
FEEDBACK_PRIORITIES = ["Low", "Medium", "High", "Urgent"]
DEFAULT_FEEDBACK_CATEGORY = "Other"


class Feedback(Document):
	def autoname(self):
		self.name = "FDB-" + frappe.generate_hash(length=8)

	def before_insert(self):
		if not self.submitted_by:
			self.submitted_by = frappe.session.user
		# Every item is created "New" and only moves via the dedicated
		# move_status action - creation never accepts a status (design.md
		# "Open Questions"). Moderator/Product Owner lifecycles then move it
		# through the split moderation/roadmap state machine (design.md
		# Decision 14, permissions.py MODERATOR_TRANSITIONS/
		# PRODUCT_OWNER_TRANSITIONS).
		self.status = "New"
		if not self.vote_count:
			self.vote_count = 0
		if not self.priority:
			self.priority = "Medium"
		if not self.category:
			self.category = DEFAULT_FEEDBACK_CATEGORY
		self.is_anonymous = 1 if self.is_anonymous else 0
		self._derive_organization_and_product()
		if self.is_anonymous and self.organization:
			# Generate/reuse this submitter's alias for the organization up
			# front (spec: feedback-anonymity "Persistent Alias") rather than
			# lazily on first read - the mapping must exist as soon as the
			# anonymous item does.
			get_or_create_alias(self.submitted_by, self.organization)

	def validate(self):
		self._derive_organization_and_product()
		self._validate_category()
		self._validate_priority()

	def _derive_organization_and_product(self):
		# organization/product are always resolved from board -> product ->
		# organization, never accepted from the client, and re-derived on
		# every save so they can never drift from the current board
		# (design.md Decision 2). board is read-only after creation, so this
		# is a no-op re-derivation on subsequent saves, not a moving target.
		if not self.board:
			return
		product = frappe.db.get_value("Board", self.board, "product")
		self.product = product
		self.organization = frappe.db.get_value("Product", product, "organization") if product else None

	def _validate_category(self):
		if not self.category or not frappe.db.exists("Feedback Category", self.category):
			frappe.throw(_("Invalid feedback category."), frappe.ValidationError)

	def _validate_priority(self):
		if self.priority not in FEEDBACK_PRIORITIES:
			frappe.throw(_("Invalid priority."), frappe.ValidationError)
