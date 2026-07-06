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
	context.title = "Products"
	context.csrf_token = frappe.sessions.get_csrf_token()

	organization = org_context.get_active_organization()
	membership = get_active_membership(frappe.session.user, organization) if organization else None
	context.can_manage = bool(membership and membership.role in PRODUCT_ROLES)
