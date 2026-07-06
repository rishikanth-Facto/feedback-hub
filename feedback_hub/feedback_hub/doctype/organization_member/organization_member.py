import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class OrganizationMember(Document):
	def autoname(self):
		self.name = "OM-" + frappe.generate_hash(length=8)

	def before_insert(self):
		self._set_membership_key()

	def before_save(self):
		self._set_membership_key()

	def _set_membership_key(self):
		# Race-safe composite uniqueness alongside the friendly check in
		# validate() (design.md Decision 4): the DB-level unique index on this
		# field is what actually prevents a concurrent duplicate.
		identity = self.user or self.invited_email
		self.membership_key = f"{self.organization}:{identity}"

	def validate(self):
		self._check_duplicate_membership()
		self._apply_joined_on()
		self._guard_last_active_admin()

	def _check_duplicate_membership(self):
		identity_filters = {"organization": self.organization, "name": ["!=", self.name or ""]}
		if self.user:
			identity_filters["user"] = self.user
		elif self.invited_email:
			identity_filters["invited_email"] = self.invited_email
		else:
			return
		if frappe.db.exists("Organization Member", identity_filters):
			frappe.throw(
				_("A membership already exists for this user in this organization."), frappe.DuplicateEntryError
			)

	def _apply_joined_on(self):
		previous = self.get_doc_before_save()
		became_active = self.status == "Active" and (not previous or previous.status != "Active")
		if became_active and not self.joined_on:
			self.joined_on = now_datetime()

	def _guard_last_active_admin(self):
		previous = self.get_doc_before_save()
		if not previous or previous.status != "Active" or previous.role != "Organization Admin":
			return
		still_active_admin = self.status == "Active" and self.role == "Organization Admin"
		if still_active_admin:
			return
		other_active_admins = frappe.db.count(
			"Organization Member",
			{
				"organization": self.organization,
				"role": "Organization Admin",
				"status": "Active",
				"name": ["!=", self.name],
			},
		)
		if not other_active_admins:
			frappe.throw(
				_("Cannot change this member: the organization must always have at least one active Organization Admin."),
				frappe.ValidationError,
			)

	def on_trash(self):
		if frappe.flags.get("force_delete_organization"):
			# The whole Organization (and every membership in it) is being
			# force-deleted at once - "must always have an admin" doesn't
			# apply when there will be no organization left to guard.
			return
		if self.status != "Active" or self.role != "Organization Admin":
			return
		other_active_admins = frappe.db.count(
			"Organization Member",
			{
				"organization": self.organization,
				"role": "Organization Admin",
				"status": "Active",
				"name": ["!=", self.name],
			},
		)
		if not other_active_admins:
			frappe.throw(
				_("Cannot remove the last active Organization Admin of an organization."), frappe.ValidationError
			)
