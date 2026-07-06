import frappe
from frappe import _

from feedback_hub.organization.context import get_active_organization
from feedback_hub.product.permissions import (
	get_permission_query_conditions_board,
	resolve_role_in_active_organization,
)

# Feedback permission checks delegate to the Board's own has_permission hook
# rather than re-deriving the role/visibility matrix a third time (design.md
# Decision 2) - "can this caller read this Feedback item" is always "can
# this caller read its Board," never a separately maintained rule.

# Status lifecycle is split into two independently-owned halves (design.md
# Decision 14): Moderator runs the moderation triage (New -> Under Review ->
# Approved/Rejected), Product Owner runs the roadmap (Approved -> Planned ->
# In Progress -> Released -> Closed). Each map is {current_status: {allowed
# next statuses}} - a role may only move a Feedback item along its own half
# of the lifecycle, never into the other's territory. Organization Admin
# bypasses both maps entirely (full access, any status, per the objective's
# permission table).
MODERATOR_TRANSITIONS = {
	"New": {"Under Review"},
	"Under Review": {"Approved", "Rejected"},
}
PRODUCT_OWNER_TRANSITIONS = {
	"Approved": {"Planned"},
	"Planned": {"In Progress"},
	"In Progress": {"Released"},
	"Released": {"Closed"},
}
# Roles that can move *some* Feedback item to *some* status - used only as a
# cosmetic "is dragging worth offering at all" hint by www controllers
# (board_detail.py/feedback_list.py) to decide whether Kanban cards render as
# draggable. The real, transition-aware gate is can_move_status below, which
# service.move_status always calls regardless of what the client attempted.
STATUS_MOVE_ROLES = ("Organization Admin", "Moderator", "Product Owner")


def can_access_board(board, ptype="read", user=None):
	doc = frappe.get_doc("Board", board)
	return bool(frappe.has_permission("Board", ptype, doc, user=user))


def require_board_read(board):
	"""Shared by service.py (Feedback CRUD) and vote.py/comment.py/follow.py
	(Module 5 engagement actions) - moved here from service.py, where it
	originated as a private helper used by a single file, once a second
	module needed the identical check (avoid duplicating it four times)."""
	if not can_access_board(board, "read"):
		frappe.throw(_("You do not have access to this board."), frappe.PermissionError)


def can_move_status_role(board, user=None):
	"""Cosmetic only (see STATUS_MOVE_ROLES) - never the real authorization
	for an actual status change, that's can_move_status(doc, new_status)."""
	user = user or frappe.session.user
	doc = frappe.get_doc("Board", board)
	organization = frappe.db.get_value("Product", doc.product, "organization") if doc.product else None
	role = resolve_role_in_active_organization(user, organization)
	return role in STATUS_MOVE_ROLES


def can_move_status(doc, new_status, user=None):
	"""Real gate for service.move_status: is `user` allowed to move this
	specific Feedback item from its current doc.status to new_status. Split
	moderation/roadmap ownership (design.md Decision 14) - Moderator and
	Product Owner each only get their own half of the lifecycle, and Product
	Owner is further scoped to products they own (unchanged from the earlier
	edit/delete scoping)."""
	user = user or frappe.session.user
	role = resolve_role_in_active_organization(user, doc.organization)
	if not role:
		return False
	if role == "Organization Admin":
		return True
	if role == "Moderator":
		return new_status in MODERATOR_TRANSITIONS.get(doc.status, set())
	if role == "Product Owner":
		return is_product_owner_of_board(doc.board, user) and new_status in PRODUCT_OWNER_TRANSITIONS.get(doc.status, set())
	return False


def _board_of(feedback_doc):
	return feedback_doc.board


def is_product_owner_of_board(board, user=None):
	user = user or frappe.session.user
	product = frappe.db.get_value("Board", board, "product")
	if not product:
		return False
	return frappe.db.get_value("Product", product, "product_owner") == user


# ---------------------------------------------------------------------------
# Engagement (voting/commenting/following) - Module 5 design.md Decision 9
# ---------------------------------------------------------------------------


def _require_not_archived(feedback_doc):
	"""Feedback itself has no archived state of its own - only its Product
	does (product.utils.PRODUCT_STATUSES). Voting/commenting is blocked once
	the owning Product is archived; a deleted Feedback item is already
	unreachable (frappe.get_doc raises DoesNotExistError before this runs)."""
	if feedback_doc.product and frappe.db.get_value("Product", feedback_doc.product, "status") == "Archived":
		frappe.throw(_("This feedback item's product has been archived."), frappe.ValidationError)


def can_engage(doc, user=None):
	"""Vote/comment/reply/follow: any role with board read access - the
	objective's permission table only ever restricts *deletion of others'
	content*, never the baseline engagement actions themselves."""
	return can_access_board(doc.board, "read", user=user)


def can_edit_comment(comment_doc, user=None):
	"""Author-only, no role bypass - Moderator/Product Owner/Organization
	Admin may delete another user's comment (can_delete_comment below) but
	never silently edit its content (design.md Decision 7)."""
	user = user or frappe.session.user
	return comment_doc.commented_by == user


def can_delete_comment(comment_doc, user=None):
	"""Author of the comment, or Moderator/Organization Admin anywhere in the
	organization, or Product Owner scoped to products they own (design.md
	Decision 9)."""
	user = user or frappe.session.user
	if comment_doc.commented_by == user:
		return True
	role = resolve_role_in_active_organization(user, comment_doc.organization)
	if not role:
		return False
	if role in ("Moderator", "Organization Admin"):
		return True
	if role == "Product Owner":
		board = frappe.db.get_value("Feedback", comment_doc.feedback, "board")
		return bool(board) and is_product_owner_of_board(board, user)
	return False


def can_edit_or_delete_feedback(doc, ptype, user=None):
	"""Single source of truth for the Feedback role matrix (design.md
	Decision 6), shared by has_permission_feedback below and by
	service.update_feedback/delete_feedback's own explicit gate (the same
	bypass-after-explicit-check shape already used for move_status)."""
	user = user or frappe.session.user
	role = resolve_role_in_active_organization(user, doc.organization)
	if not role:
		return False
	if role == "Organization Admin":
		return True
	if role == "Product Owner":
		# Edit only, never delete (revised: deleting customer feedback is an
		# audit-trail risk - Product Owner's equivalent of "removing" an item
		# is closing it out via the roadmap lifecycle's Released -> Closed
		# transition, can_move_status below, not frappe.delete_doc).
		if ptype == "delete":
			return False
		return is_product_owner_of_board(doc.board, user)
	if role == "Moderator":
		# Read+write on any Feedback in the organization, never delete.
		return ptype == "write"
	if role == "Customer":
		# Only before a Moderator has taken any moderation action - once the
		# lifecycle has moved past "New", discussions/votes/planning may
		# already be underway (revised from the original "Under Review"
		# window, which was itself the initial/creation status prior to this
		# revision).
		return doc.submitted_by == user and doc.status == "New"
	return False  # Developer: read-only, per the objective's permission table


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def has_permission_feedback(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	ptype = ptype or "read"
	if ptype in ("write", "delete"):
		return can_edit_or_delete_feedback(doc, ptype, user=user)
	# create and read both reduce to "can this user see/act on this board" -
	# plus a Customer can always read their own submission (design.md
	# Decision 6).
	return doc.submitted_by == user or can_access_board(_board_of(doc), "read", user=user)


def get_permission_query_conditions_feedback(user=None):
	# Deliberately NOT OR'd with "submitted_by = user" here (unlike the
	# single-doc has_permission_feedback check above): that would let a
	# user's own historical submissions leak across organizations in list/
	# search results whenever they belong to more than one, defeating the
	# active-organization scoping this whole module is built on (feedback-
	# permissions spec "Cross-Organization Access Is Prevented"). Reading a
	# specific, already-known Feedback id you authored is fine (has_permission_
	# feedback); listing across organizations you don't currently have active
	# is not.
	user = user or frappe.session.user
	return "`tabFeedback`.board in (select `name` from `tabBoard` where {condition})".format(
		condition=get_permission_query_conditions_board(user)
	)


# ---------------------------------------------------------------------------
# Feedback Vote
# ---------------------------------------------------------------------------


def has_permission_feedback_vote(doc, ptype=None, user=None, debug=False, **kwargs):
	ptype = ptype or "read"
	if ptype in ("write", "delete"):
		# toggle_vote flips is_deleted (or, for a direct hard delete, calls
		# frappe.delete_doc) via ignore_permissions=True after its own
		# explicit check (Module 5 design.md Decision 3), so this hook is
		# never the real gate for mutation - denying by default avoids a
		# Desk-only caller changing/deleting someone else's vote directly.
		return False
	board = frappe.db.get_value("Feedback", doc.feedback, "board") if doc.feedback else None
	return can_access_board(board, "read", user=user) if board else False


def get_permission_query_conditions_feedback_vote(user=None):
	user = user or frappe.session.user
	# Belt-and-suspenders organization isolation (Module 5 design.md Decision
	# 9), on top of the existing board-visibility subquery: a cheap indexed
	# equality against the caller's currently active organization.
	active_organization = get_active_organization()
	return (
		"`tabFeedback Vote`.organization = {organization} and "
		"`tabFeedback Vote`.feedback in (select `name` from `tabFeedback` where board in "
		"(select `name` from `tabBoard` where {condition}))"
	).format(organization=frappe.db.escape(active_organization or ""), condition=get_permission_query_conditions_board(user))


# ---------------------------------------------------------------------------
# Feedback Comment
# ---------------------------------------------------------------------------


def has_permission_feedback_comment(doc, ptype=None, user=None, debug=False, **kwargs):
	ptype = ptype or "read"
	if ptype == "write":
		return can_edit_comment(doc, user=user)
	if ptype == "delete":
		return can_delete_comment(doc, user=user)
	board = frappe.db.get_value("Feedback", doc.feedback, "board") if doc.feedback else None
	return can_access_board(board, "read", user=user) if board else False


def get_permission_query_conditions_feedback_comment(user=None):
	user = user or frappe.session.user
	# Belt-and-suspenders organization isolation (Module 5 design.md Decision
	# 9), on top of the existing board-visibility subquery.
	active_organization = get_active_organization()
	return (
		"`tabFeedback Comment`.organization = {organization} and "
		"`tabFeedback Comment`.feedback in (select `name` from `tabFeedback` where board in "
		"(select `name` from `tabBoard` where {condition}))"
	).format(organization=frappe.db.escape(active_organization or ""), condition=get_permission_query_conditions_board(user))


# ---------------------------------------------------------------------------
# Feedback Follower
# ---------------------------------------------------------------------------


def has_permission_feedback_follower(doc, ptype=None, user=None, debug=False, **kwargs):
	user = user or frappe.session.user
	ptype = ptype or "read"
	if ptype == "delete":
		# A user may only remove their own follow - never someone else's.
		return doc.user == user
	board = frappe.db.get_value("Feedback", doc.feedback, "board") if doc.feedback else None
	return can_access_board(board, "read", user=user) if board else False


def get_permission_query_conditions_feedback_follower(user=None):
	user = user or frappe.session.user
	active_organization = get_active_organization()
	return (
		"`tabFeedback Follower`.organization = {organization} and "
		"`tabFeedback Follower`.feedback in (select `name` from `tabFeedback` where board in "
		"(select `name` from `tabBoard` where {condition}))"
	).format(organization=frappe.db.escape(active_organization or ""), condition=get_permission_query_conditions_board(user))
