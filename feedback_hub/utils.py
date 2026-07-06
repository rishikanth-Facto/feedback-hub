import re

import frappe
from frappe import _

PASSWORD_MIN_LENGTH = 8
SPECIAL_CHARACTERS = r"""!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?"""


def api_response(success, message, data=None):
	"""Standard JSON envelope used by every feedback_hub-authored endpoint."""
	return {"success": bool(success), "message": message, "data": data or {}}


def validate_password_strength(password):
	"""Enforce: min 8 chars, >=1 uppercase, >=1 lowercase, >=1 digit, >=1 special char.

	Returns None if the password passes. Returns a user-facing error message
	string (naming the failed rule) otherwise - callers decide whether to
	frappe.throw or return it via api_response.
	"""
	if not password or len(password) < PASSWORD_MIN_LENGTH:
		return _("Password must be at least {0} characters long.").format(PASSWORD_MIN_LENGTH)
	if not re.search(r"[A-Z]", password):
		return _("Password must contain at least one uppercase letter.")
	if not re.search(r"[a-z]", password):
		return _("Password must contain at least one lowercase letter.")
	if not re.search(r"\d", password):
		return _("Password must contain at least one digit.")
	if not re.search(f"[{SPECIAL_CHARACTERS}]", password):
		return _("Password must contain at least one special character.")
	return None


IMPLICIT_ROLES = {"All", "Guest"}


def display_roles(user):
	"""frappe.get_roles() always includes the implicit 'All' role, and Website
	Users also implicitly get 'Guest' (for baseline permission checks) - strip
	both so the UI only shows the meaningful assigned role(s)."""
	return [r for r in frappe.get_roles(user) if r not in IMPLICIT_ROLES]


def require_login():
	"""Raise if the caller is not authenticated. Use at the top of any
	feedback_hub whitelisted method that is not explicitly Guest-allowed."""
	if frappe.session.user == "Guest":
		frappe.throw(_("You must be logged in to access this resource."), frappe.PermissionError)
