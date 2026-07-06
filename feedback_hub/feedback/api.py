import frappe
from frappe import _

from feedback_hub.feedback import service
from feedback_hub.feedback import comment as comment_module
from feedback_hub.feedback import vote as vote_module
from feedback_hub.organization.api import handle_errors
from feedback_hub.organization.context import get_active_organization
from feedback_hub.utils import api_response, require_login

# Reuses feedback_hub.organization.api.handle_errors and
# feedback_hub.utils.{api_response, require_login} directly, same thin-
# wrapper pattern as product/api.py - no re-definition.


@frappe.whitelist(methods=["POST"])
@handle_errors
def create_feedback(board=None, title=None, description=None, category=None, priority=None, is_anonymous=False):
	require_login()
	data = service.create_feedback(
		board, title, description=description, category=category, priority=priority, is_anonymous=is_anonymous
	)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Feedback submitted."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_feedback(
	board=None,
	organization=None,
	product=None,
	category=None,
	priority=None,
	status=None,
	search=None,
	order_by="creation",
	order_dir="desc",
	page=1,
	page_size=20,
):
	require_login()
	data = service.list_feedback(
		board=board,
		organization=organization,
		product=product,
		category=category,
		priority=priority,
		status=status,
		search=search,
		order_by=order_by,
		order_dir=order_dir,
		page=page,
		page_size=page_size,
	)
	return api_response(True, _("Feedback fetched."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def get_feedback(feedback=None):
	require_login()
	data = service.get_feedback(feedback)
	return api_response(True, _("Feedback fetched."), data)


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_feedback(feedback=None, title=None, description=None, category=None, priority=None, is_anonymous=None):
	require_login()
	data = service.update_feedback(
		feedback, title=title, description=description, category=category, priority=priority, is_anonymous=is_anonymous
	)
	return api_response(True, _("Feedback updated."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def delete_feedback(feedback=None):
	require_login()
	data = service.delete_feedback(feedback)
	return api_response(True, _("Feedback deleted."), data)


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def move_status(feedback=None, status=None):
	require_login()
	data = service.move_status(feedback, status)
	return api_response(True, _("Status updated."), data)


@frappe.whitelist(methods=["POST"])
@handle_errors
def toggle_vote(feedback=None):
	# Thin re-export onto Module 5's vote.py (Feedback Vote's soft-delete
	# toggle now lives there) - fh_kanban.js/feedback_detail.js only read
	# res.success/res.message from this call, never res.data, so the response
	# shape change (vote_count -> total_votes) is safe for them unchanged.
	require_login()
	data = vote_module._toggle_vote(feedback)
	message = _("Vote recorded.") if data.get("voted") else _("Vote removed.")
	return api_response(True, message, data)


@frappe.whitelist(methods=["POST"])
@handle_errors
def add_comment(feedback=None, comment_text=None):
	# Thin re-export onto Module 5's comment.py (Feedback Comment now supports
	# threading/edit/soft-delete) - fh_kanban.js/feedback_detail.js render
	# res.data via commented_by/comment_text, so this legacy endpoint keeps
	# projecting that original shape rather than the new tree-node shape
	# comment.create_comment returns.
	require_login()
	doc = comment_module._create_comment(feedback, comment_text)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Comment added."), {field: doc.get(field) for field in service.COMMENT_FIELDS})


@frappe.whitelist(methods=["POST"])
@handle_errors
def add_attachment(feedback=None):
	require_login()
	uploaded = frappe.request.files.get("file") if frappe.request else None
	if not uploaded:
		return api_response(False, _("No file uploaded."))

	data = service.add_attachment(feedback, uploaded.filename or "", uploaded.read())
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Attachment added."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def remove_attachment(feedback=None, attachment=None):
	require_login()
	data = service.remove_attachment(feedback, attachment)
	return api_response(True, _("Attachment removed."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_deleted_feedback(organization=None):
	require_login()
	data = service.list_deleted_feedback(organization or get_active_organization())
	return api_response(True, _("Deleted feedback fetched."), data)
