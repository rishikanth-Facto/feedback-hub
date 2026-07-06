import re

import frappe

BOARD_VISIBILITIES = ["Public", "Private", "Internal"]
PRODUCT_STATUSES = ["Active", "Archived"]


def slugify(value):
	value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
	return value or "item"


def generate_unique_slug(name, scope_field, scope_value, doctype="Product", exclude_name=None):
	"""Slugify name and append a numeric suffix on collision, scoped to
	{scope_field: scope_value} rather than globally (design.md Decision 6) -
	generalizes organization.utils.generate_unique_slug's algorithm since
	Product/Board slugs are only unique within their parent (Organization/
	Product), not across the whole table."""
	base = slugify(name)
	candidate = base
	suffix = 2
	while frappe.db.exists(
		doctype, {"slug": candidate, scope_field: scope_value, "name": ["!=", exclude_name or ""]}
	):
		candidate = f"{base}-{suffix}"
		suffix += 1
	return candidate
