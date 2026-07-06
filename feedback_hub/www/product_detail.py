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

	context.no_header = True
	context.csrf_token = frappe.sessions.get_csrf_token()

	product = frappe.form_dict.get("id")
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
		# Products are invisible to every role except Organization Admin/
		# Product Owner (spec: product-board-permissions) - the detail page
		# never reveals existence to anyone else, same not-found shape
		# organization_detail.py uses for non-members.
		context.title = "Product Not Found"
		context.not_found = True
		return

	doc = frappe.get_doc("Product", product)
	context.title = doc.product_name
	context.product = doc
