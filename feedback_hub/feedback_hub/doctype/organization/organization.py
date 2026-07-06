import frappe
from frappe import _
from frappe.model.document import Document

from feedback_hub.organization.utils import generate_unique_slug


class Organization(Document):
	def autoname(self):
		# Frappe's built-in autoname: "hash" has no prefix support (confirmed
		# against frappe/model/naming.py) - a controller autoname() method is
		# the supported way to get a prefixed, non-sequential docname
		# (design.md Decision 1).
		self.name = "ORG-" + frappe.generate_hash(length=8)

	def before_insert(self):
		if not self.slug:
			self.slug = generate_unique_slug(self.organization_name)
		if not self.organization_owner:
			self.organization_owner = frappe.session.user
		if not self.status:
			self.status = "Active"

	def validate(self):
		if frappe.db.exists("Organization", {"organization_name": self.organization_name, "name": ["!=", self.name]}):
			frappe.throw(_("An organization with this name already exists."), frappe.DuplicateEntryError)

	def after_insert(self):
		# The creator is always the first Active Organization Admin so an
		# organization is never left without one (spec: organization-lifecycle).
		frappe.get_doc(
			{
				"doctype": "Organization Member",
				"organization": self.name,
				"user": self.organization_owner,
				"role": "Organization Admin",
				"status": "Active",
				"joined_on": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)

	def on_trash(self):
		active_members = frappe.db.count("Organization Member", {"organization": self.name, "status": "Active"})
		if active_members and not frappe.flags.get("force_delete_organization"):
			frappe.throw(
				_(
					"Cannot delete organization {0}: it still has {1} active member(s). "
					"Remove them first or use force delete."
				).format(self.organization_name, active_members),
				frappe.LinkExistsError,
			)
		if frappe.flags.get("force_delete_organization"):
			for member in frappe.get_all("Organization Member", filters={"organization": self.name}, pluck="name"):
				frappe.delete_doc("Organization Member", member, ignore_permissions=True, force=True)
