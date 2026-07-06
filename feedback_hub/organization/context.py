import frappe

from feedback_hub.organization.permissions import get_active_membership

SESSION_KEY = "active_organization"


def get_active_organization():
	"""Resolve the caller's active organization from session data, re-validating
	on every call that the membership is still Active (design.md Decision 9) -
	a suspended/removed member is never allowed to keep acting inside an org
	just because they switched into it earlier."""
	organization = frappe.session.data.get(SESSION_KEY)
	if not organization:
		return _auto_resolve_sole_active_organization()
	if not get_active_membership(frappe.session.user, organization):
		clear_active_organization()
		return None
	return organization


def _auto_resolve_sole_active_organization():
	"""If the caller has never explicitly selected an active organization
	but is an Active member of exactly one, treat that one as implicitly
	active. Without this, a single-org user - the common case - would have
	no way to reach organization-scoped features at all, since the
	org-switcher UI only appears once a caller belongs to 2+ organizations
	(org_switcher.js). Only applies when nothing was ever explicitly stored
	in session - a since-revoked explicit selection still clears to None
	above rather than silently jumping to a different organization."""
	memberships = frappe.get_all(
		"Organization Member", filters={"user": frappe.session.user, "status": "Active"}, pluck="organization"
	)
	return memberships[0] if len(memberships) == 1 else None


def set_active_organization(organization):
	# frappe.session IS the session's persisted data dict (frappe/sessions.py);
	# mutating it alone isn't durable until Session.update() flushes it, which
	# is normally throttled - force=True flushes immediately, same as core's
	# own set_impersonated() (design.md Decision 8). session_obj only exists
	# during a real HTTP request (frappe/auth.py) - it's absent in console/
	# test contexts, where the in-memory mutation alone is already sufficient.
	frappe.session.data[SESSION_KEY] = organization
	_flush_session()


def clear_active_organization():
	frappe.session.data[SESSION_KEY] = None
	_flush_session()


def _flush_session():
	session_obj = getattr(frappe.local, "session_obj", None)
	if session_obj:
		session_obj.update(force=True)
