from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime, validate_email_address

from feedback_hub.organization import context, permissions
from feedback_hub.organization.utils import ORG_ROLES, INVITATION_VALIDITY_SECONDS, generate_invitation_token

ORGANIZATION_FIELDS = [
	"name",
	"organization_name",
	"slug",
	"description",
	"logo",
	"status",
	"organization_owner",
	"owner",
	"creation",
	"modified",
]

MEMBER_FIELDS = ["name", "organization", "user", "invited_email", "role", "status", "invited_by", "joined_on"]


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------


def create_organization(organization_name, description=None, logo=None):
	if not organization_name or not organization_name.strip():
		frappe.throw(_("Organization Name is required."), frappe.ValidationError)

	doc = frappe.get_doc(
		{
			"doctype": "Organization",
			"organization_name": organization_name.strip(),
			"description": description,
			"logo": logo,
		}
	)
	doc.insert()
	return doc.as_dict()


def get_organization(organization):
	doc = frappe.get_doc("Organization", organization)
	frappe.has_permission("Organization", "read", doc, throw=True)
	return {field: doc.get(field) for field in ORGANIZATION_FIELDS}


def list_organizations():
	memberships = frappe.get_all(
		"Organization Member",
		filters={"user": frappe.session.user, "status": "Active"},
		fields=["organization", "role"],
	)
	role_by_org = {m.organization: m.role for m in memberships}
	if not role_by_org:
		return []

	orgs = frappe.get_list(
		"Organization",
		filters={"name": ["in", list(role_by_org.keys())]},
		fields=ORGANIZATION_FIELDS,
		order_by="modified desc",
	)
	for org in orgs:
		org["role"] = role_by_org.get(org["name"])
	return orgs


def update_organization(organization, organization_name=None, description=None, logo=None, status=None):
	permissions.require_org_admin(organization)
	doc = frappe.get_doc("Organization", organization)
	if organization_name:
		doc.organization_name = organization_name.strip()
	if description is not None:
		doc.description = description
	if logo is not None:
		doc.logo = logo
	if status:
		if status not in ("Active", "Inactive"):
			frappe.throw(_("Invalid status."), frappe.ValidationError)
		doc.status = status
	doc.save()
	return doc.as_dict()


def delete_organization(organization, force=False):
	permissions.require_org_admin(organization)

	if not force:
		# Excludes the calling admin: an admin deleting their own org isn't an
		# "active member still around to be surprised" - the guard is about
		# *other* active members, who would otherwise silently lose access.
		active_members = frappe.db.count(
			"Organization Member",
			{"organization": organization, "status": "Active", "user": ["!=", frappe.session.user]},
		)
		if active_members:
			frappe.throw(
				_(
					"Cannot delete organization: {0} active member(s) still exist. "
					"Remove them first or pass force=true to force delete."
				).format(active_members),
				frappe.LinkExistsError,
			)
		frappe.db.set_value("Organization", organization, "status", "Inactive")
		return {"organization": organization, "deleted": False, "status": "Inactive"}

	frappe.flags.force_delete_organization = True
	try:
		frappe.delete_doc("Organization", organization, ignore_permissions=True)
	finally:
		frappe.flags.force_delete_organization = False
	return {"organization": organization, "deleted": True}


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


def list_members(organization=None):
	organization = organization or context.get_active_organization()
	if not organization:
		frappe.throw(_("No active organization selected. Switch to an organization first."), frappe.ValidationError)

	membership = permissions.get_active_membership(frappe.session.user, organization)
	if not membership:
		frappe.throw(_("You are not a member of this organization."), frappe.PermissionError)

	filters = {"organization": organization}
	if membership.role != "Organization Admin":
		# Non-admins can only read their own membership row (spec: organization-permissions).
		filters["user"] = frappe.session.user

	return frappe.get_list("Organization Member", filters=filters, fields=MEMBER_FIELDS, order_by="creation asc")


def update_member(member_id, role=None, status=None):
	member = frappe.get_doc("Organization Member", member_id)
	permissions.require_org_admin(member.organization)

	if role:
		if role not in ORG_ROLES:
			frappe.throw(_("Invalid role."), frappe.ValidationError)
		member.role = role
	if status:
		if status not in ("Pending", "Active", "Suspended"):
			frappe.throw(_("Invalid status."), frappe.ValidationError)
		member.status = status
	member.save(ignore_permissions=True)
	return {field: member.get(field) for field in MEMBER_FIELDS}


def remove_member(member_id):
	member = frappe.get_doc("Organization Member", member_id)
	permissions.require_org_admin(member.organization)
	frappe.delete_doc("Organization Member", member_id, ignore_permissions=True)
	return {"name": member_id, "removed": True}


# ---------------------------------------------------------------------------
# Invitation
# ---------------------------------------------------------------------------


def invite_member(organization, email, role):
	permissions.require_org_admin(organization)

	if not email:
		frappe.throw(_("Email is required."), frappe.ValidationError)
	validate_email_address(email, throw=True)
	if role not in ORG_ROLES:
		frappe.throw(_("Invalid role."), frappe.ValidationError)

	email = email.strip().lower()
	existing_user = frappe.db.exists("User", email)

	identity_filters = {"organization": organization, "user": existing_user} if existing_user else {
		"organization": organization,
		"invited_email": email,
	}
	existing_membership = frappe.db.get_value("Organization Member", identity_filters, ["name", "status"], as_dict=True)
	if existing_membership:
		if existing_membership.status == "Active":
			frappe.throw(_("This person is already an active member of the organization."), frappe.DuplicateEntryError)
		frappe.throw(_("A pending invitation already exists for this email."), frappe.DuplicateEntryError)

	token = generate_invitation_token()
	expires_on = now_datetime() + timedelta(seconds=INVITATION_VALIDITY_SECONDS)

	member = frappe.get_doc(
		{
			"doctype": "Organization Member",
			"organization": organization,
			"user": existing_user or None,
			"invited_email": None if existing_user else email,
			"role": role,
			"status": "Pending",
			"invited_by": frappe.session.user,
			"invitation_token": token,
			"invitation_expires_on": expires_on,
		}
	)
	member.insert(ignore_permissions=True)

	try:
		_send_invitation_email(email, organization, token)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Feedback Hub: invitation email failed")
		frappe.throw(_("We couldn't send the invitation email. Please try again."))

	return {field: member.get(field) for field in MEMBER_FIELDS}


def _send_invitation_email(email, organization, token):
	org_name = frappe.db.get_value("Organization", organization, "organization_name")
	url = frappe.utils.get_url(f"/accept_invitation?token={token}")
	frappe.sendmail(
		recipients=[email],
		subject=_("You've been invited to join {0} on Feedback Hub").format(org_name),
		message=_(
			"You've been invited to join <b>{0}</b> on Feedback Hub.<br><br>"
			'<a href="{1}">{1}</a><br><br>'
			"This invitation expires in 7 days."
		).format(org_name, url),
		now=True,
	)


def accept_invitation(token):
	if not token:
		return {"result": "invalid"}

	member = frappe.db.get_value(
		"Organization Member",
		{"invitation_token": token},
		["name", "organization", "user", "invited_email", "status", "invitation_expires_on"],
		as_dict=True,
	)
	if not member or member.status != "Pending":
		return {"result": "invalid"}

	if member.invitation_expires_on and now_datetime() > get_datetime(member.invitation_expires_on):
		return {"result": "expired"}

	target_email = (member.user or member.invited_email or "").lower()
	current_user = frappe.session.user

	if current_user == "Guest":
		account_exists = bool(member.user) or bool(frappe.db.exists("User", target_email))
		return {"result": "login_required" if account_exists else "signup_required", "email": target_email}

	if current_user.lower() != target_email:
		return {"result": "identity_mismatch"}

	if frappe.db.exists("Organization Member", {"organization": member.organization, "user": current_user, "name": ["!=", member.name]}):
		return {"result": "duplicate_membership"}

	doc = frappe.get_doc("Organization Member", member.name)
	doc.user = current_user
	doc.invited_email = None
	doc.status = "Active"
	doc.invitation_token = None
	doc.invitation_expires_on = None
	doc.save(ignore_permissions=True)

	return {"result": "accepted", "organization": member.organization}


# ---------------------------------------------------------------------------
# Active organization / switching
# ---------------------------------------------------------------------------


def switch_organization(organization):
	if not organization:
		frappe.throw(_("Organization is required."), frappe.ValidationError)

	membership = permissions.get_active_membership(frappe.session.user, organization)
	if not membership:
		frappe.throw(_("You are not an active member of this organization."), frappe.PermissionError)

	status = frappe.db.get_value("Organization", organization, "status")
	if status != "Active":
		frappe.throw(_("Cannot switch to an inactive organization."), frappe.ValidationError)

	context.set_active_organization(organization)
	return {"organization": organization}
