import re

import frappe

INVITATION_VALIDITY_SECONDS = 7 * 24 * 60 * 60  # 7 days

ORG_ROLES = ["Organization Admin", "Product Owner", "Moderator", "Developer", "Customer"]
MEMBER_STATUSES = ["Pending", "Active", "Suspended"]


def slugify(value):
	value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
	return value or "org"


def generate_unique_slug(organization_name, exclude_name=None):
	"""Slugify organization_name and append a numeric suffix on collision
	(design.md Decision 2). Runs once, in before_insert, so slugs stay stable."""
	base = slugify(organization_name)
	candidate = base
	suffix = 2
	while frappe.db.exists("Organization", {"slug": candidate, "name": ["!=", exclude_name or ""]}):
		candidate = f"{base}-{suffix}"
		suffix += 1
	return candidate


def generate_invitation_token():
	return frappe.generate_hash(length=32)
