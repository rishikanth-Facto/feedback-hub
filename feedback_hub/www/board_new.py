import frappe
import frappe.sessions

from feedback_hub.organization import context as org_context
from feedback_hub.organization.permissions import get_active_membership
from feedback_hub.product.permissions import PRODUCT_ROLES

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login"
		raise frappe.Redirect

	product = frappe.form_dict.get("product")
	organization = org_context.get_active_organization()
	membership = get_active_membership(frappe.session.user, organization) if organization else None

	valid = (
		product
		and membership
		and membership.role in PRODUCT_ROLES
		and frappe.db.exists("Product", product)
		and frappe.db.get_value("Product", product, "organization") == organization
	)
	if not valid:
		# Board create is only reachable through a Product a caller can
		# already manage - redirect rather than reveal existence, same
		# not-found shape as product_detail.py for anyone else.
		frappe.local.flags.redirect_location = "/products"
		raise frappe.Redirect

	doc = frappe.get_doc("Product", product)
	context.no_header = True
	context.title = "New Board"
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.product = doc
	context.product_archived = doc.status == "Archived"
