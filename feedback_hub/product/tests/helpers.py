import frappe

from feedback_hub.organization import service as org_service


def make_active_organization(owner_email, org_name):
	"""Create an Organization owned by owner_email and make it that user's
	active organization - every Product/Board operation resolves the active
	organization, so tests need this every time (design.md Decision 3)."""
	frappe.set_user(owner_email)
	org = org_service.create_organization(org_name)
	org_service.switch_organization(org["name"])
	return org


def add_active_member(organization, admin_email, user_email, role):
	"""Invite + immediately activate a membership, mirroring organization/
	tests' own invite-then-activate pattern. Leaves the caller set to
	admin_email so setup calls can be chained."""
	frappe.set_user(admin_email)
	invite = org_service.invite_member(organization, user_email, role)
	frappe.db.set_value("Organization Member", invite["name"], "status", "Active")
	return invite


def switch_to_organization(user_email, organization):
	"""Set user_email's active organization context and leave the caller set
	to user_email so the next service call runs as that user."""
	frappe.set_user(user_email)
	org_service.switch_organization(organization)
