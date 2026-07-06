import frappe
import frappe.sessions

no_cache = 1


def get_context(context):
	# Deliberately no Guest redirect here (spec: organization-permissions
	# "Guest Access Restricted To Invitation Acceptance") - the page itself
	# renders for anyone; feedback_hub.organization.api.accept_invitation
	# (allow_guest=True) decides what actually happens with the token.
	context.no_header = True
	context.title = "Accept Invitation"
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.token = frappe.form_dict.get("token") or ""
