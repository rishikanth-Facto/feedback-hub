import functools

import frappe
from frappe import _

from feedback_hub.api import ALLOWED_PHOTO_EXTENSIONS, MAX_PHOTO_SIZE_BYTES
from feedback_hub.organization import permissions, service
from feedback_hub.utils import api_response, require_login

# ---------------------------------------------------------------------------
# Centralized error handling (design.md Decision 11): every endpoint below is
# a thin wrapper - parse input, call feedback_hub.organization.service, format
# the result/error through the shared api_response envelope with the HTTP
# status code that matches the failure (spec: organization-lifecycle
# "Structured API Responses").
# ---------------------------------------------------------------------------

_STATUS_BY_EXCEPTION = (
	(frappe.PermissionError, 403),
	(frappe.DoesNotExistError, 404),
	(frappe.DuplicateEntryError, 409),
	(frappe.LinkExistsError, 409),
	(frappe.ValidationError, 400),
)


def handle_errors(fn):
	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except Exception as e:
			for exc_class, status_code in _STATUS_BY_EXCEPTION:
				if isinstance(e, exc_class):
					frappe.clear_messages()
					frappe.local.response["http_status_code"] = status_code
					return api_response(False, str(e) or _("Request failed."))
			raise

	return wrapper


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def create_organization(organization_name=None, description=None, logo=None):
	require_login()
	data = service.create_organization(organization_name, description=description, logo=logo)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Organization created."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_organizations():
	require_login()
	data = service.list_organizations()
	return api_response(True, _("Organizations fetched."), {"organizations": data})


@frappe.whitelist(methods=["GET"])
@handle_errors
def get_organization(organization=None):
	require_login()
	data = service.get_organization(organization)
	return api_response(True, _("Organization fetched."), data)


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_organization(organization=None, organization_name=None, description=None, logo=None, status=None):
	require_login()
	data = service.update_organization(
		organization, organization_name=organization_name, description=description, logo=logo, status=status
	)
	return api_response(True, _("Organization updated."), data)


@frappe.whitelist(methods=["POST"])
@handle_errors
def upload_logo(organization=None):
	require_login()
	permissions.require_org_admin(organization)

	# Same File-doctype pattern as feedback_hub.api.update_profile_photo -
	# reuses its extension/size constants rather than redefining them.
	uploaded = frappe.request.files.get("file") if frappe.request else None
	if not uploaded:
		return api_response(False, _("No file uploaded."))

	filename = uploaded.filename or ""
	extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
	if extension not in ALLOWED_PHOTO_EXTENSIONS:
		return api_response(
			False, _("Unsupported file type. Allowed types: {0}").format(", ".join(sorted(ALLOWED_PHOTO_EXTENSIONS)))
		)

	content = uploaded.read()
	if len(content) > MAX_PHOTO_SIZE_BYTES:
		return api_response(False, _("File is too large. Maximum size is 2 MB."))

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": "Organization",
			"attached_to_name": organization,
			"attached_to_field": "logo",
			"is_private": 0,
		}
	)
	file_doc.flags.ignore_permissions = True
	file_doc.save()

	frappe.db.set_value("Organization", organization, "logo", file_doc.file_url)

	return api_response(True, _("Logo updated."), {"logo": file_doc.file_url})


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def delete_organization(organization=None, force=False):
	require_login()
	data = service.delete_organization(organization, force=frappe.utils.cint(force))
	message = _("Organization deleted.") if data.get("deleted") else _("Organization deactivated.")
	return api_response(True, message, data)


# ---------------------------------------------------------------------------
# Membership management
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_members(organization=None):
	require_login()
	data = service.list_members(organization)
	return api_response(True, _("Members fetched."), {"members": data})


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_member(member=None, role=None, status=None):
	require_login()
	data = service.update_member(member, role=role, status=status)
	return api_response(True, _("Member updated."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def remove_member(member=None):
	require_login()
	data = service.remove_member(member)
	return api_response(True, _("Member removed."), data)


# ---------------------------------------------------------------------------
# Invitation
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def invite_member(organization=None, email=None, role=None):
	require_login()
	data = service.invite_member(organization, email, role)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Invitation sent."), data)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@handle_errors
def accept_invitation(token=None):
	# Guest-reachable (spec: organization-permissions "Guest Access Restricted
	# To Invitation Acceptance") - service.accept_invitation only ever mutates
	# data for an authenticated caller whose identity matches the invitation
	# (design.md Decision 7).
	result = service.accept_invitation(token)
	messages = {
		"accepted": _("Invitation accepted. Welcome to the organization!"),
		"invalid": _("This invitation link is invalid."),
		"expired": _("This invitation has expired. Please ask an admin to resend it."),
		"identity_mismatch": _("This invitation was sent to a different account."),
		"duplicate_membership": _("You already have a membership in this organization."),
		"login_required": _("Please log in to accept this invitation."),
		"signup_required": _("Please sign up first, then accept this invitation."),
	}
	success = result["result"] == "accepted"
	return api_response(success, messages[result["result"]], result)


# ---------------------------------------------------------------------------
# Active organization / switching
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def switch_organization(organization=None):
	require_login()
	data = service.switch_organization(organization)
	return api_response(True, _("Active organization switched."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def get_active_organization():
	# Small read-only helper for the org-switcher UI (Section 16) to know
	# which option to preselect - not part of the original REST list, but
	# needed since context.get_active_organization() is otherwise server-only.
	require_login()
	from feedback_hub.organization import context

	return api_response(True, _("Active organization fetched."), {"organization": context.get_active_organization()})
