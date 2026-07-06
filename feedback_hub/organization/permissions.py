import frappe

# Controller has_permission hooks can only DENY permission that role-level
# DocPerm already granted, never grant beyond it (frappe/permissions.py
# has_controller_permissions docstring) - see hooks.py: both doctypes grant
# base create/read/write/delete to role "All", and everything below narrows
# that down to real organization membership (design.md Decision 10).


def get_active_membership(user, organization):
	if not organization:
		return None
	return frappe.db.get_value(
		"Organization Member",
		{"organization": organization, "user": user, "status": "Active"},
		["name", "role"],
		as_dict=True,
	)


def is_org_admin(user, organization):
	membership = get_active_membership(user, organization)
	return bool(membership and membership.role == "Organization Admin")


def require_org_admin(organization, user=None):
	user = user or frappe.session.user
	if not is_org_admin(user, organization):
		frappe.throw(
			frappe._("You must be an Organization Admin of this organization to perform this action."),
			frappe.PermissionError,
		)


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------


def has_permission_organization(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	ptype = ptype or "read"
	if ptype == "create":
		# No existing org to check membership against yet - any authenticated
		# user may create one (DocPerm "All" already grants create=1).
		return None
	membership = get_active_membership(user, doc.name)
	if not membership:
		return False
	if ptype in ("write", "delete"):
		return membership.role == "Organization Admin"
	return True


def get_permission_query_conditions_organization(user=None):
	user = user or frappe.session.user
	return (
		"`tabOrganization`.name in ("
		"select `organization` from `tabOrganization Member` "
		f"where `user` = {frappe.db.escape(user)} and `status` = 'Active')"
	)


# ---------------------------------------------------------------------------
# Organization Member
# ---------------------------------------------------------------------------


def has_permission_organization_member(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	ptype = ptype or "read"
	if is_org_admin(user, doc.organization):
		return True
	if ptype in ("write", "delete", "create"):
		return False
	return doc.user == user


def get_permission_query_conditions_organization_member(user=None):
	user = user or frappe.session.user
	return (
		"`tabOrganization Member`.organization in ("
		"select `organization` from `tabOrganization Member` "
		f"where `user` = {frappe.db.escape(user)} and `status` = 'Active')"
	)
