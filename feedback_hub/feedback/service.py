import frappe
from frappe import _
from frappe.utils import cint

from feedback_hub.feedback.anonymity import get_or_create_alias
from feedback_hub.feedback.comment import TOMBSTONE_TEXT, _create_comment
from feedback_hub.feedback.permissions import (
	can_edit_or_delete_feedback,
	can_move_status,
	require_board_read,
)
from feedback_hub.feedback.vote import _toggle_vote
from feedback_hub.feedback_hub.doctype.feedback.feedback import FEEDBACK_PRIORITIES, FEEDBACK_STATUSES
from feedback_hub.organization.permissions import get_active_membership
from feedback_hub.product.permissions import resolve_role_in_active_organization

# Roles with elevated read access to a Feedback item beyond the submitter
# themselves - Moderator/Product Owner/Organization Admin (objective's
# permission table: "Moderator - View all feedback... Can see: ... Reporter,
# Anonymous Flag, Attachments, Activity History").
ELEVATED_ROLES = ("Organization Admin", "Product Owner", "Moderator")

FEEDBACK_FIELDS = [
	"name",
	"title",
	"description",
	"category",
	"priority",
	"status",
	"is_anonymous",
	"board",
	"organization",
	"product",
	"submitted_by",
	"vote_count",
	"creation",
	"modified",
]
COMMENT_FIELDS = ["name", "feedback", "commented_by", "comment_text", "creation", "is_deleted"]
ATTACHMENT_FIELDS = ["name", "file", "file_name", "file_url", "file_type", "file_size"]

ORDER_BY_FIELDS = {"creation", "modified", "title", "priority", "vote_count", "status"}
DEFAULT_PAGE_SIZE = 20

MAX_ATTACHMENTS = 5
ALLOWED_ATTACHMENT_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "txt", "doc", "docx"}
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024


_require_board_read = require_board_read

def _is_org_admin(user, organization):
	membership = get_active_membership(user, organization) if organization else None
	return bool(membership and membership.role == "Organization Admin")


def _resolve_role(viewer, organization):
	return resolve_role_in_active_organization(viewer, organization)


def _project_fields(doc_or_dict, viewer=None):
	"""Field projection for a single Feedback record. `submitted_by` keeps its
	original real-value-or-None semantics (real to the submitter/an
	Organization Admin, None to everyone else) so existing callers/tests are
	unaffected. `reporter` is the role-aware display identity (spec: feedback-
	anonymity "Persistent Alias"): real identity to the submitter or an
	Organization Admin, a stable per-organization alias to Customer/Moderator/
	Product Owner when the item is anonymous (revised: a fellow Customer
	benefits from telling anonymous participants apart in a discussion thread,
	same as Moderator/Product Owner already could - only the real identity is
	sensitive, not the pseudonym), and hidden (None) only to a Developer, who
	has no discussion/moderation role here. The stored value and its version
	history are never touched, only this response-shaping step ever hides it."""
	viewer = viewer or frappe.session.user
	data = {field: doc_or_dict.get(field) for field in FEEDBACK_FIELDS}
	organization = data.get("organization")
	real_submitted_by = data.get("submitted_by")
	is_owner = real_submitted_by == viewer
	is_admin = _is_org_admin(viewer, organization)
	anonymous = bool(data.get("is_anonymous"))

	if anonymous and not (is_owner or is_admin):
		data["submitted_by"] = None
		role = _resolve_role(viewer, organization)
		data["reporter"] = (
			get_or_create_alias(real_submitted_by, organization) if role in ("Customer", "Moderator", "Product Owner") else None
		)
	else:
		data["reporter"] = real_submitted_by
	return data


def _require_feedback_write(doc, ptype="write"):
	if not can_edit_or_delete_feedback(doc, ptype):
		frappe.throw(_("You do not have permission to modify this feedback item."), frappe.PermissionError)


# ---------------------------------------------------------------------------
# Feedback CRUD (spec: feedback-lifecycle)
# ---------------------------------------------------------------------------


def create_feedback(board, title, description=None, category=None, priority=None, is_anonymous=False):
	_require_board_read(board)
	if not title or not title.strip():
		frappe.throw(_("Title is required."), frappe.ValidationError)
	if not description or not str(description).strip():
		frappe.throw(_("Description is required."), frappe.ValidationError)

	doc = frappe.get_doc(
		{
			"doctype": "Feedback",
			"title": title.strip(),
			"description": str(description).strip(),
			"board": board,
			"category": category,
			"priority": priority,
			"is_anonymous": 1 if cint(is_anonymous) else 0,
		}
	)
	doc.insert()
	return _project_fields(doc)


def _get_activity_history(feedback_name):
	"""Reuses Frappe's own change-tracking (Version, enabled via
	track_changes=1 on the Feedback doctype) as the Moderator/Product Owner/
	Organization Admin "Activity History" / audit trail, rather than building
	a parallel bespoke log."""
	versions = frappe.get_all(
		"Version",
		filters={"ref_doctype": "Feedback", "docname": feedback_name},
		fields=["owner", "creation", "data"],
		order_by="creation asc",
	)
	history = []
	for version in versions:
		changed = frappe.parse_json(version.data or "{}").get("changed") or []
		history.append(
			{
				"by": version.owner,
				"at": version.creation,
				"changes": [{"field": row[0], "from": row[1], "to": row[2]} for row in changed],
			}
		)
	return history


def get_feedback(feedback):
	doc = frappe.get_doc("Feedback", feedback)
	frappe.has_permission("Feedback", "read", doc, throw=True)

	viewer = frappe.session.user
	role = _resolve_role(viewer, doc.organization)
	is_owner = doc.submitted_by == viewer
	is_admin = _is_org_admin(viewer, doc.organization)
	role_elevated = is_admin or role in ELEVATED_ROLES

	data = _project_fields(doc)
	data["has_voted"] = bool(frappe.db.exists("Feedback Vote", {"feedback": doc.name, "user": viewer, "is_deleted": 0}))
	data["comments"] = frappe.get_list(
		"Feedback Comment", filters={"feedback": doc.name}, fields=COMMENT_FIELDS, order_by="creation asc"
	)
	# Legacy flat shape (Module 5 design.md 12.6) - feedback_detail.js/
	# fh_kanban.js render this list directly via commented_by/comment_text and
	# have no concept of threading, so it stays flat (roots + replies mixed,
	# unchanged) with only a tombstone substitution for soft-deleted comments.
	for comment in data["comments"]:
		if comment.get("is_deleted"):
			comment["comment_text"] = TOMBSTONE_TEXT
	# Attachments are visible to the submitter themselves (it's their own
	# upload), to Moderator/Product Owner/Organization Admin, and to anyone
	# else who can read this item because its Board is Public (revised: a
	# screenshot attached to a public bug report should be visible to whoever
	# can already see that report, not only its author/moderators). Activity
	# History stays moderation-only - even the submitter does not see it,
	# since it can reveal moderator/owner actions on their item (objective's
	# permission table: Customer "Cannot see: Moderation information").
	board_is_public = frappe.db.get_value("Board", doc.board, "visibility") == "Public"
	data["attachments"] = (
		frappe.get_all("Feedback Attachment", filters={"parent": doc.name}, fields=ATTACHMENT_FIELDS, order_by="idx asc")
		if (is_owner or role_elevated or board_is_public)
		else []
	)
	data["activity_history"] = _get_activity_history(doc.name) if role_elevated else []
	return data


def update_feedback(feedback, title=None, description=None, category=None, priority=None, is_anonymous=None):
	doc = frappe.get_doc("Feedback", feedback)
	_require_feedback_write(doc, "write")

	if title is not None:
		if not title.strip():
			frappe.throw(_("Title is required."), frappe.ValidationError)
		doc.title = title.strip()
	if description is not None:
		if not str(description).strip():
			frappe.throw(_("Description is required."), frappe.ValidationError)
		doc.description = str(description).strip()
	if category is not None:
		doc.category = category
	if priority is not None:
		if priority not in FEEDBACK_PRIORITIES:
			frappe.throw(_("Invalid priority."), frappe.ValidationError)
		doc.priority = priority
	if is_anonymous is not None:
		doc.is_anonymous = 1 if cint(is_anonymous) else 0

	# has_permission_feedback's write branch already mirrors this same rule
	# (can_edit_or_delete_feedback) - ignore_permissions=True here only skips
	# the redundant re-check, the same bypass-after-explicit-check pattern as
	# move_status/toggle_vote. ignore_version=False overrides Frappe's default
	# of skipping Version rows under frappe.flags.in_test - Activity History
	# (spec: feedback-permissions "Moderation Fields") must exist for tests
	# and production alike, not only outside the test runner.
	doc.save(ignore_permissions=True, ignore_version=False)
	return _project_fields(doc)


def delete_feedback(feedback):
	doc = frappe.get_doc("Feedback", feedback)
	_require_feedback_write(doc, "delete")

	_delete_all_attachments(doc)
	frappe.delete_doc("Feedback", feedback, ignore_permissions=True)
	return {"name": feedback}


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
	page_size=DEFAULT_PAGE_SIZE,
):
	if board:
		_require_board_read(board)

	if order_by not in ORDER_BY_FIELDS:
		frappe.throw(_("Invalid sort field."), frappe.ValidationError)
	if order_dir not in ("asc", "desc"):
		frappe.throw(_("Invalid sort direction."), frappe.ValidationError)

	filters = {}
	for fieldname, value in (
		("board", board),
		("organization", organization),
		("product", product),
		("category", category),
		("priority", priority),
		("status", status),
	):
		if value:
			filters[fieldname] = value

	or_filters = None
	if search:
		term = f"%{search}%"
		or_filters = {"title": ["like", term], "description": ["like", term]}

	page = cint(page) or 1
	# page_size <= 0 means "no limit" (Frappe's own limit_page_length=0/None
	# convention - see frappe.model.db_query.DatabaseQuery) rather than being
	# coerced up to DEFAULT_PAGE_SIZE - the pre-existing Kanban board view
	# (fh_kanban.js) relies on getting every item for its board in one call,
	# exactly like it did before this endpoint gained pagination.
	page_size = cint(page_size)
	unlimited = page_size <= 0
	limit_start = 0 if unlimited else (page - 1) * page_size

	# frappe.get_list (not get_all) so permission_query_conditions_feedback
	# always scopes rows to what the caller may see, regardless of which
	# filters were explicitly requested (a filter for an inaccessible
	# organization/product/board simply yields zero rows, never a leak).
	items = frappe.get_list(
		"Feedback",
		filters=filters,
		or_filters=or_filters,
		fields=FEEDBACK_FIELDS,
		order_by=f"{order_by} {order_dir}",
		limit_start=limit_start,
		limit_page_length=0 if unlimited else page_size,
	)
	total = frappe.get_list(
		"Feedback", filters=filters, or_filters=or_filters, fields=["count(name) as total"]
	)[0]["total"]

	if items:
		item_names = [item["name"] for item in items]
		voted_names = set(
			frappe.get_all(
				"Feedback Vote",
				filters={"feedback": ["in", item_names], "user": frappe.session.user, "is_deleted": 0},
				pluck="feedback",
			)
		)
		comment_counts = {
			row["feedback"]: row["count"]
			for row in frappe.get_all(
				"Feedback Comment",
				filters={"feedback": ["in", item_names], "is_deleted": 0},
				fields=["feedback", "count(name) as count"],
				group_by="feedback",
			)
		}
		for item in items:
			item["has_voted"] = item["name"] in voted_names
			item["comment_count"] = comment_counts.get(item["name"], 0)

	feedback_list = []
	for item in items:
		projected = _project_fields(item)
		projected["has_voted"] = item.get("has_voted", False)
		projected["comment_count"] = item.get("comment_count", 0)
		feedback_list.append(projected)

	return {"feedback": feedback_list, "total": total, "page": page, "page_size": page_size}


# ---------------------------------------------------------------------------
# Status management (Kanban card move) - Organization Admin/Product Owner only
# ---------------------------------------------------------------------------


def move_status(feedback, status):
	doc = frappe.get_doc("Feedback", feedback)
	if status not in FEEDBACK_STATUSES:
		frappe.throw(_("Invalid status."), frappe.ValidationError)
	if not can_move_status(doc, status):
		# Split moderation/roadmap lifecycle (design.md Decision 14) - the
		# message is deliberately generic rather than naming the caller's
		# role, since the same call can fail for different reasons (Moderator
		# tried a roadmap transition, Product Owner tried a moderation one, or
		# the transition just isn't valid from the item's current status).
		frappe.throw(
			_("You are not permitted to move this feedback item to that status."),
			frappe.PermissionError,
		)

	doc.status = status
	# has_permission_feedback denies plain "write" to most roles - can_move_status
	# above is the real, stricter gate for this one specific mutation, same
	# bypass-after-explicit-check pattern as organization.service.update_member
	# (design.md Decision 3). ignore_version=False - see update_feedback.
	doc.save(ignore_permissions=True, ignore_version=False)
	return _project_fields(doc)


# ---------------------------------------------------------------------------
# Voting
# ---------------------------------------------------------------------------


def toggle_vote(feedback):
	# Thin re-export onto Module 5's vote.py (Feedback Vote now soft-deletes
	# on toggle instead of hard-deleting) - reshaped to this function's
	# original {feedback, voted, vote_count} contract so pre-existing callers
	# (test_feedback_voting.py) keep working unmodified.
	result = _toggle_vote(feedback)
	return {"feedback": result["feedback"], "voted": result["voted"], "vote_count": result["total_votes"]}


# ---------------------------------------------------------------------------
# Commenting
# ---------------------------------------------------------------------------


def add_comment(feedback, comment_text):
	# Thin re-export onto Module 5's comment.py (Feedback Comment now supports
	# threading/edit/soft-delete) - reshaped to this function's original flat
	# COMMENT_FIELDS contract so pre-existing callers (test_feedback_commenting.py)
	# keep working unmodified.
	comment = _create_comment(feedback, comment_text)
	return {field: comment.get(field) for field in COMMENT_FIELDS}


# ---------------------------------------------------------------------------
# Attachments (spec: feedback-attachments)
# ---------------------------------------------------------------------------


def _validate_attachment(filename, content):
	extension = filename.rsplit(".", 1)[-1].lower() if filename and "." in filename else ""
	if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
		frappe.throw(
			_("Unsupported file type. Allowed types: {0}").format(", ".join(sorted(ALLOWED_ATTACHMENT_EXTENSIONS))),
			frappe.ValidationError,
		)
	if len(content) > MAX_ATTACHMENT_SIZE_BYTES:
		frappe.throw(_("File is too large. Maximum size is 5 MB."), frappe.ValidationError)
	return extension


def add_attachment(feedback, filename, content):
	doc = frappe.get_doc("Feedback", feedback)
	_require_feedback_write(doc, "write")

	if len(doc.attachments) >= MAX_ATTACHMENTS:
		frappe.throw(_("A feedback item can have at most {0} attachments.").format(MAX_ATTACHMENTS), frappe.ValidationError)

	extension = _validate_attachment(filename, content)

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": "Feedback",
			"attached_to_name": doc.name,
			"is_private": 1,
		}
	)
	file_doc.flags.ignore_permissions = True
	file_doc.save()

	doc.append(
		"attachments",
		{
			"file": file_doc.name,
			"file_name": file_doc.file_name,
			"file_url": file_doc.file_url,
			"file_type": extension,
			"file_size": len(content),
		},
	)
	doc.save(ignore_permissions=True)

	return {field: doc.attachments[-1].get(field) for field in ATTACHMENT_FIELDS}


def remove_attachment(feedback, attachment_row):
	doc = frappe.get_doc("Feedback", feedback)
	_require_feedback_write(doc, "write")

	row = next((row for row in doc.attachments if row.name == attachment_row), None)
	if not row:
		frappe.throw(_("Attachment not found."), frappe.DoesNotExistError)

	file_name = row.file
	doc.attachments.remove(row)
	doc.save(ignore_permissions=True)

	if file_name and frappe.db.exists("File", file_name):
		frappe.delete_doc("File", file_name, ignore_permissions=True)

	return {"name": attachment_row}


def _delete_all_attachments(doc):
	file_names = [row.file for row in doc.attachments if row.file]
	for file_name in file_names:
		if frappe.db.exists("File", file_name):
			frappe.delete_doc("File", file_name, ignore_permissions=True)


# ---------------------------------------------------------------------------
# Deleted feedback recovery (Organization Admin only) - objective's
# permission table: "Organization Admin - Can see: ... Deleted feedback".
# ---------------------------------------------------------------------------


def list_deleted_feedback(organization):
	if not organization or not _is_org_admin(frappe.session.user, organization):
		frappe.throw(
			_("You must be an Organization Admin of this organization to view deleted feedback."),
			frappe.PermissionError,
		)

	# Reuses Frappe's own Deleted Document table (populated automatically by
	# frappe.delete_doc for every doctype) instead of soft-deleting Feedback
	# or building a parallel deleted-items table.
	rows = frappe.get_all(
		"Deleted Document",
		filters={"deleted_doctype": "Feedback"},
		fields=["deleted_name", "owner", "creation", "data"],
		order_by="creation desc",
	)
	deleted = []
	for row in rows:
		payload = frappe.parse_json(row.data or "{}")
		if payload.get("organization") != organization:
			continue
		deleted.append(
			{
				"name": row.deleted_name,
				"title": payload.get("title"),
				"board": payload.get("board"),
				"status": payload.get("status"),
				"submitted_by": payload.get("submitted_by"),
				"deleted_by": row.owner,
				"deleted_at": row.creation,
			}
		)
	return deleted
