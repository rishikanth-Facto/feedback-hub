import mimetypes

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from feedback_hub.feedback.events import emit_event
from feedback_hub.feedback.permissions import (
	_require_not_archived,
	can_delete_comment,
	can_edit_comment,
	require_board_read,
)
from feedback_hub.feedback.timeline import record_activity
from feedback_hub.organization.api import handle_errors
from feedback_hub.utils import api_response, require_login

MAX_COMMENT_LENGTH = 10000
DEFAULT_PAGE_SIZE = 20

MAX_COMMENT_ATTACHMENTS = 5
ALLOWED_COMMENT_ATTACHMENT_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf", "txt", "mp4", "webm", "mov"}
MAX_COMMENT_ATTACHMENT_SIZE_BYTES = 20 * 1024 * 1024

COMMENT_TREE_FIELDS = [
	"name",
	"feedback",
	"parent_comment",
	"commented_by",
	"comment_text",
	"is_deleted",
	"edited_at",
	"edited_by",
	"creation",
]
ATTACHMENT_FIELDS = ["name", "file", "filename", "mime_type", "size"]

TOMBSTONE_TEXT = "This comment was deleted."


def _validate_content(content):
	if not content or not str(content).strip():
		frappe.throw(_("Comment text is required."), frappe.ValidationError)
	if len(content) > MAX_COMMENT_LENGTH:
		frappe.throw(_("Comment is too long. Maximum length is {0} characters.").format(MAX_COMMENT_LENGTH), frappe.ValidationError)


def _project_attachment(row):
	file_url = frappe.db.get_value("File", row.get("file"), "file_url") if row.get("file") else None
	return {
		"name": row.get("name"),
		"filename": row.get("filename"),
		"mime_type": row.get("mime_type"),
		"size": row.get("size"),
		"preview_url": file_url,
		"download_url": file_url,
	}


def _project_comment(row, reply_count=0, attachments=None):
	deleted = bool(row.get("is_deleted"))
	return {
		"name": row.get("name"),
		"feedback": row.get("feedback"),
		"parent_comment": row.get("parent_comment") or None,
		"author": row.get("commented_by"),
		"content": TOMBSTONE_TEXT if deleted else row.get("comment_text"),
		"creation": row.get("creation"),
		"edited": bool(row.get("edited_at")),
		"edited_at": row.get("edited_at"),
		"edited_by": row.get("edited_by"),
		"reply_count": reply_count,
		"attachments": attachments or [],
	}


def _create_comment(feedback, content, parent_comment=None):
	"""Returns the raw inserted Document (not a projected dict) so callers can
	shape the response themselves - this module's own create_comment API uses
	_project_comment's new tree-friendly shape, while api.py's legacy
	add_comment re-export needs the original commented_by/comment_text shape
	fh_kanban.js/feedback_detail.js already render (Module 5 design.md's
	backward-compatibility requirement)."""
	doc = frappe.get_doc("Feedback", feedback)  # raises DoesNotExistError if missing
	_require_not_archived(doc)
	require_board_read(doc.board)
	_validate_content(content)

	if parent_comment:
		# Checked eagerly here, not left to the doctype's own validate() -
		# Frappe's generic Link-field integrity check (_validate_links) runs
		# before any controller validate() during insert() and would raise
		# LinkValidationError for a missing parent_comment before our own
		# DoesNotExistError ever had a chance to. The doctype's validate()
		# still re-checks the same-feedback rule as defense in depth for
		# direct Desk-created comments that bypass this service function.
		parent_feedback = frappe.db.get_value("Feedback Comment", parent_comment, "feedback")
		if not parent_feedback:
			frappe.throw(_("Parent comment does not exist."), frappe.DoesNotExistError)
		if parent_feedback != feedback:
			frappe.throw(_("Parent comment must belong to the same feedback item."), frappe.ValidationError)

	comment = frappe.get_doc(
		{
			"doctype": "Feedback Comment",
			"feedback": feedback,
			"comment_text": str(content).strip(),
			"parent_comment": parent_comment or None,
		}
	)
	comment.insert()

	if parent_comment:
		record_activity(feedback, "Reply Added")
		emit_event("reply", doc, comment=comment.name, parent_comment=parent_comment)
	else:
		record_activity(feedback, "Comment Added")
		emit_event("comment", doc, comment=comment.name)

	return comment


def _update_comment(comment, content):
	doc = frappe.get_doc("Feedback Comment", comment)
	if not can_edit_comment(doc):
		frappe.throw(_("You do not have permission to edit this comment."), frappe.PermissionError)
	_validate_content(content)

	doc.comment_text = str(content).strip()
	doc.edited_at = now_datetime()
	doc.edited_by = frappe.session.user
	# ignore_version=False forces the Version row even under frappe.flags.in_test
	# (Module 4's own precedent) - edit history must exist deterministically.
	doc.save(ignore_permissions=True, ignore_version=False)
	record_activity(doc.feedback, "Comment Edited")
	return _project_comment(doc.as_dict())


def _delete_comment(comment):
	doc = frappe.get_doc("Feedback Comment", comment)
	if not can_delete_comment(doc):
		frappe.throw(_("You do not have permission to delete this comment."), frappe.PermissionError)

	# Soft delete only - content/edited_at/edited_by are never touched, so the
	# original text survives in the record and its Version history (design.md
	# Decision 6). The tombstone is a read-time projection, not a write.
	doc.is_deleted = 1
	doc.save(ignore_permissions=True, ignore_version=False)
	record_activity(doc.feedback, "Comment Deleted")
	return _project_comment(doc.as_dict())


def get_comment(comment):
	doc = frappe.get_doc("Feedback Comment", comment)
	frappe.has_permission("Feedback Comment", "read", doc, throw=True)
	reply_count = frappe.db.count("Feedback Comment", {"parent_comment": doc.name})
	attachments = [
		_project_attachment(row)
		for row in frappe.get_all("Feedback Comment Attachment", filters={"parent": doc.name}, fields=ATTACHMENT_FIELDS, order_by="idx asc")
	]
	return _project_comment(doc.as_dict(), reply_count=reply_count, attachments=attachments)


def _fetch_descendants(root_ids):
	"""Level-by-level BFS expansion (design.md Decision 5): one query per
	depth level actually present in the data, not per comment, bounded by
	real thread depth rather than a hard-coded limit."""
	all_descendants = []
	frontier = list(root_ids)
	while frontier:
		children = frappe.get_all(
			"Feedback Comment",
			filters={"parent_comment": ["in", frontier]},
			fields=COMMENT_TREE_FIELDS,
			order_by="creation asc",
		)
		if not children:
			break
		all_descendants.extend(children)
		frontier = [c["name"] for c in children]
	return all_descendants


def _list_comments(feedback, page=1, page_size=DEFAULT_PAGE_SIZE):
	doc = frappe.get_doc("Feedback", feedback)  # raises DoesNotExistError if missing
	require_board_read(doc.board)

	page = cint(page) or 1
	page_size = cint(page_size) or DEFAULT_PAGE_SIZE
	root_filters = {"feedback": feedback, "parent_comment": ["is", "not set"]}

	roots = frappe.get_all(
		"Feedback Comment",
		filters=root_filters,
		fields=COMMENT_TREE_FIELDS,
		order_by="creation asc",
		limit_start=(page - 1) * page_size,
		limit_page_length=page_size,
	)
	total = frappe.db.count("Feedback Comment", root_filters)

	root_ids = [row["name"] for row in roots]
	descendants = _fetch_descendants(root_ids)
	all_rows = roots + descendants
	all_ids = [row["name"] for row in all_rows]

	reply_counts = {}
	attachments_by_comment = {}
	if all_ids:
		for row in frappe.get_all(
			"Feedback Comment",
			filters={"parent_comment": ["in", all_ids]},
			fields=["parent_comment", "count(name) as count"],
			group_by="parent_comment",
		):
			reply_counts[row["parent_comment"]] = row["count"]

		for row in frappe.get_all(
			"Feedback Comment Attachment", filters={"parent": ["in", all_ids]}, fields=["parent", *ATTACHMENT_FIELDS], order_by="idx asc"
		):
			attachments_by_comment.setdefault(row["parent"], []).append(_project_attachment(row))

	nodes = {}
	for row in all_rows:
		nodes[row["name"]] = _project_comment(
			row, reply_count=reply_counts.get(row["name"], 0), attachments=attachments_by_comment.get(row["name"], [])
		)
		nodes[row["name"]]["replies"] = []

	tree = []
	for row in all_rows:
		node = nodes[row["name"]]
		parent = row.get("parent_comment")
		if parent and parent in nodes:
			nodes[parent]["replies"].append(node)
		elif not parent:
			tree.append(node)

	return {"comments": tree, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Attachments (spec: feedback-comment-attachments)
# ---------------------------------------------------------------------------


def _add_comment_attachment(comment, filename, content):
	doc = frappe.get_doc("Feedback Comment", comment)
	if not can_edit_comment(doc):
		frappe.throw(_("You do not have permission to attach files to this comment."), frappe.PermissionError)

	if len(doc.attachments) >= MAX_COMMENT_ATTACHMENTS:
		frappe.throw(_("A comment can have at most {0} attachments.").format(MAX_COMMENT_ATTACHMENTS), frappe.ValidationError)

	extension = filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
	if extension not in ALLOWED_COMMENT_ATTACHMENT_EXTENSIONS:
		frappe.throw(
			_("Unsupported file type. Allowed types: {0}").format(", ".join(sorted(ALLOWED_COMMENT_ATTACHMENT_EXTENSIONS))),
			frappe.ValidationError,
		)
	if len(content) > MAX_COMMENT_ATTACHMENT_SIZE_BYTES:
		frappe.throw(_("File is too large. Maximum size is 20 MB."), frappe.ValidationError)

	mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": "Feedback Comment",
			"attached_to_name": doc.name,
			"is_private": 1,
		}
	)
	file_doc.flags.ignore_permissions = True
	file_doc.save()

	doc.append("attachments", {"file": file_doc.name, "filename": filename, "mime_type": mime_type, "size": len(content)})
	doc.save(ignore_permissions=True)

	return _project_attachment(doc.attachments[-1].as_dict())


def _remove_comment_attachment(comment, attachment_row):
	doc = frappe.get_doc("Feedback Comment", comment)
	if not can_edit_comment(doc):
		frappe.throw(_("You do not have permission to modify this comment's attachments."), frappe.PermissionError)

	row = next((row for row in doc.attachments if row.name == attachment_row), None)
	if not row:
		frappe.throw(_("Attachment not found."), frappe.DoesNotExistError)

	file_name = row.file
	doc.attachments.remove(row)
	doc.save(ignore_permissions=True)

	if file_name and frappe.db.exists("File", file_name):
		frappe.delete_doc("File", file_name, ignore_permissions=True)

	return {"name": attachment_row}


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def create_comment(feedback=None, content=None, parent_comment=None):
	require_login()
	doc = _create_comment(feedback, content, parent_comment=parent_comment)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Comment added."), _project_comment(doc.as_dict()))


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_comment(comment=None, content=None):
	require_login()
	data = _update_comment(comment, content)
	return api_response(True, _("Comment updated."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def delete_comment(comment=None):
	require_login()
	data = _delete_comment(comment)
	return api_response(True, _("Comment deleted."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_comments(feedback=None, page=1, page_size=DEFAULT_PAGE_SIZE):
	require_login()
	data = _list_comments(feedback, page=page, page_size=page_size)
	return api_response(True, _("Comments fetched."), data)


@frappe.whitelist(methods=["POST"])
@handle_errors
def add_comment_attachment(comment=None):
	require_login()
	uploaded = frappe.request.files.get("file") if frappe.request else None
	if not uploaded:
		return api_response(False, _("No file uploaded."))

	data = _add_comment_attachment(comment, uploaded.filename or "", uploaded.read())
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Attachment added."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def remove_comment_attachment(comment=None, attachment=None):
	require_login()
	data = _remove_comment_attachment(comment, attachment)
	return api_response(True, _("Attachment removed."), data)
