import frappe

from feedback_hub.organization.context import get_active_organization
from feedback_hub.organization.permissions import get_active_membership

# Feedback Category is a global master list (not organization-scoped): every
# logged-in user can read it (needed to populate the category picker on the
# Create/Edit Feedback forms via the generic frappe.client.get_list, no
# bespoke list endpoint required), but only an Organization Admin (of their
# currently active organization) may create/edit/delete entries.


def has_permission_feedback_category(doc, ptype=None, user=None, debug=False, **kwargs):
	ptype = ptype or "read"
	if ptype == "read":
		return True
	user = user or frappe.session.user
	organization = get_active_organization()
	membership = get_active_membership(user, organization) if organization else None
	return bool(membership and membership.role == "Organization Admin")
