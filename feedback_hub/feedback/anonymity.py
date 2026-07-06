import random

import frappe

from feedback_hub.organization.permissions import is_org_admin

# Anonymous Alias (spec: feedback-anonymity "Persistent Alias") - a stable,
# human-friendly stand-in for a user's real identity, scoped per (user,
# organization) and reused across all of that user's future anonymous
# submissions in the same organization. The mapping itself is only ever
# readable by an Organization Admin (who can also just read the real
# submitted_by/audit trail directly) or the aliased user; every other role
# only ever sees the alias string via service._project_fields, never this
# doctype.

_ADJECTIVES = [
	"Sea", "Golden", "Silver", "Crimson", "Midnight", "Azure", "Silent", "Swift",
	"Brave", "Gentle", "Hidden", "Lunar", "Solar", "Frosty", "Scarlet", "Emerald",
	"Violet", "Amber", "Shadow", "Bright",
]
_ANIMALS = [
	"Turtle", "Owl", "Fox", "Falcon", "Otter", "Wolf", "Heron", "Panther",
	"Sparrow", "Badger", "Raven", "Lynx", "Dolphin", "Hawk", "Bear", "Deer",
	"Rabbit", "Tiger", "Eagle", "Koala",
]


def get_or_create_alias(user, organization):
	existing = frappe.db.get_value("Anonymous Alias", {"user": user, "organization": organization}, "alias")
	if existing:
		return existing

	used = set(frappe.get_all("Anonymous Alias", filters={"organization": organization}, pluck="alias"))
	candidates = [f"{adjective} {animal}" for adjective in _ADJECTIVES for animal in _ANIMALS]
	available = [candidate for candidate in candidates if candidate not in used]
	alias = random.choice(available or candidates)

	frappe.get_doc(
		{"doctype": "Anonymous Alias", "user": user, "organization": organization, "alias": alias}
	).insert(ignore_permissions=True)
	return alias


def has_permission_anonymous_alias(doc, ptype=None, user=None, debug=False, **kwargs):
	ptype = ptype or "read"
	user = user or frappe.session.user
	if ptype != "read":
		return False
	return doc.user == user or is_org_admin(user, doc.organization)
