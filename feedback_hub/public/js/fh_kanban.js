// Feedback Hub - Kanban board rendering, drag-and-drop status moves, vote
// widget, and comment thread for board_detail.html (Module 4). Hand-rolled
// HTML5 drag-and-drop, no library, per design.md Decision 10.

// "New"/"Approved"/"Rejected"/"Closed" are deliberately not columns here -
// "Approved"/"Rejected" belong to a dedicated Moderator triage screen (not
// yet built), and "New"/"Closed" are the pre-triage and fully-done edges of
// the lifecycle, neither of which is an active working state this board
// needs a column for (design.md Decision 19). Items can still reach any of
// these statuses via the API; they just don't render on this board while in
// one - they (re)appear once moved into "Under Review"..."Released".
var FH_KANBAN_STATUSES = ["Under Review", "Planned", "In Progress", "Released"];

var fhKanbanItems = [];
var fhKanbanActiveFeedbackId = null;

function fhKanbanInit() {
	if (!window.fhBoardId) return;
	fhRenderKanbanShell();
	fhLoadKanbanBoard();
	fhWireFeedbackForm();
	fhWireFeedbackDetail();
}

function fhRenderKanbanShell() {
	var tabs = document.getElementById("fh-kanban-tabs");
	var board = document.getElementById("fh-kanban-board");
	tabs.innerHTML = "";
	board.innerHTML = "";

	FH_KANBAN_STATUSES.forEach(function (status, index) {
		var tabBtn = document.createElement("button");
		tabBtn.type = "button";
		tabBtn.textContent = status;
		tabBtn.className = index === 0 ? "active" : "";
		tabBtn.addEventListener("click", function () {
			fhSetMobileActiveColumn(status);
		});
		tabs.appendChild(tabBtn);

		var column = document.createElement("div");
		column.className = "fh-kanban-column" + (index === 0 ? " fh-mobile-active" : "");
		column.dataset.status = status;

		var header = document.createElement("div");
		header.className = "fh-kanban-column-header";
		var name = document.createElement("span");
		name.textContent = status;
		var count = document.createElement("span");
		count.className = "fh-kanban-column-count";
		count.textContent = "0";
		count.id = "fh-kanban-count-" + fhKanbanSlug(status);
		header.appendChild(name);
		header.appendChild(count);
		column.appendChild(header);

		var cards = document.createElement("div");
		cards.className = "fh-kanban-cards";
		cards.id = "fh-kanban-cards-" + fhKanbanSlug(status);
		column.appendChild(cards);

		fhWireColumnDropTarget(column, cards);
		board.appendChild(column);
	});
}

function fhKanbanSlug(status) {
	return status.toLowerCase().replace(/\s+/g, "-");
}

function fhSetMobileActiveColumn(status) {
	document.querySelectorAll(".fh-kanban-tabs button").forEach(function (btn) {
		btn.classList.toggle("active", btn.textContent === status);
	});
	document.querySelectorAll(".fh-kanban-column").forEach(function (col) {
		col.classList.toggle("fh-mobile-active", col.dataset.status === status);
	});
}

function fhLoadKanbanBoard() {
	// order_by/order_dir restore the board's original oldest-first card
	// order, and page_size: 0 requests every item unpaginated - the Kanban
	// board isn't a paginated view, it renders every card in scrollable
	// columns, exactly like it did before list_feedback gained pagination
	// for the separate Feedback List page.
	fhApiCall(
		"feedback_hub.feedback.api.list_feedback",
		{ board: window.fhBoardId, order_by: "creation", order_dir: "asc", page_size: 0 },
		"GET"
	).then(function (res) {
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}
		fhKanbanItems = res.data.feedback || [];
		fhRenderKanbanCards();
	});
}

function fhRenderKanbanCards() {
	FH_KANBAN_STATUSES.forEach(function (status) {
		var container = document.getElementById("fh-kanban-cards-" + fhKanbanSlug(status));
		container.innerHTML = "";
		var items = fhKanbanItems.filter(function (item) {
			return item.status === status;
		});
		items.forEach(function (item) {
			container.appendChild(fhRenderKanbanCard(item));
		});
		document.getElementById("fh-kanban-count-" + fhKanbanSlug(status)).textContent = items.length;
	});
}

function fhRenderKanbanCard(item) {
	var card = document.createElement("div");
	card.className = "fh-kanban-card" + (window.fhCanMoveFeedback ? " fh-draggable" : "");
	card.dataset.feedbackId = item.name;
	card.draggable = !!window.fhCanMoveFeedback;

	var title = document.createElement("p");
	title.className = "fh-kanban-card-title";
	title.textContent = item.title;
	card.appendChild(title);

	var meta = document.createElement("div");
	meta.className = "fh-kanban-card-meta";

	var left = document.createElement("span");
	left.className = "fh-kanban-card-meta-left";

	var votes = document.createElement("span");
	votes.textContent = "▲ " + item.vote_count;
	left.appendChild(votes);

	var comments = document.createElement("span");
	comments.className = "fh-comment-count";
	comments.textContent = "💬 " + (item.comment_count || 0);
	left.appendChild(comments);
	meta.appendChild(left);

	var submitted = document.createElement("span");
	submitted.textContent = item.reporter || (item.is_anonymous ? "Anonymous" : "");
	meta.appendChild(submitted);

	card.appendChild(meta);

	card.addEventListener("click", function () {
		fhOpenFeedbackDetail(item.name);
	});

	if (window.fhCanMoveFeedback) {
		card.addEventListener("dragstart", function (e) {
			card.classList.add("fh-dragging");
			e.dataTransfer.setData("text/plain", item.name);
		});
		card.addEventListener("dragend", function () {
			card.classList.remove("fh-dragging");
		});
	}

	return card;
}

function fhWireColumnDropTarget(column, cards) {
	if (!window.fhCanMoveFeedback) return;

	["dragenter", "dragover"].forEach(function (evt) {
		cards.addEventListener(evt, function (e) {
			e.preventDefault();
			column.classList.add("fh-drop-target");
		});
	});
	cards.addEventListener("dragleave", function () {
		column.classList.remove("fh-drop-target");
	});
	cards.addEventListener("drop", function (e) {
		e.preventDefault();
		column.classList.remove("fh-drop-target");
		var feedbackId = e.dataTransfer.getData("text/plain");
		fhMoveFeedbackStatus(feedbackId, column.dataset.status);
	});
}

function fhMoveFeedbackStatus(feedbackId, newStatus) {
	var item = fhKanbanItems.find(function (i) {
		return i.name === feedbackId;
	});
	if (!item || item.status === newStatus) return;

	var previousStatus = item.status;
	item.status = newStatus; // optimistic update (DesignSystem.md 6.1)
	fhRenderKanbanCards();

	fhApiCall("feedback_hub.feedback.api.move_status", { feedback: feedbackId, status: newStatus }, "POST").then(
		function (res) {
			if (!res.success) {
				item.status = previousStatus; // rollback
				fhRenderKanbanCards();
				fhToast(res.message, "error");
			}
		}
	);
}

// ---------------------------------------------------------------------------
// New Feedback form
// ---------------------------------------------------------------------------

function fhWireFeedbackForm() {
	var newBtn = document.getElementById("fh-new-feedback-btn");
	var backdrop = document.getElementById("fh-feedback-modal-backdrop");
	var formSection = document.getElementById("fh-feedback-form-section");
	var detailSection = document.getElementById("fh-feedback-detail-section");
	var cancelBtn = document.getElementById("fh-feedback-form-cancel");
	var form = document.getElementById("fh-feedback-form");

	newBtn.addEventListener("click", function () {
		form.reset();
		fhHideAlert(document.getElementById("fh-feedback-form-alert"));
		formSection.style.display = "block";
		detailSection.style.display = "none";
		backdrop.className = "fh-modal-backdrop fh-visible";
	});
	cancelBtn.addEventListener("click", function () {
		backdrop.className = "fh-modal-backdrop";
	});
	backdrop.addEventListener("click", function (e) {
		if (e.target === backdrop) backdrop.className = "fh-modal-backdrop";
	});

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var alertEl = document.getElementById("fh-feedback-form-alert");
		fhHideAlert(alertEl);

		fhApiCall("feedback_hub.feedback.api.create_feedback", {
			board: window.fhBoardId,
			title: document.getElementById("feedback_title").value.trim(),
			description: document.getElementById("feedback_description").value.trim(),
		}).then(function (res) {
			if (res.success) {
				backdrop.className = "fh-modal-backdrop";
				fhToast("Feedback submitted.", "success");
				fhLoadKanbanBoard();
			} else {
				fhShowAlert(alertEl, res.message, "error");
			}
		});
	});
}

// ---------------------------------------------------------------------------
// Feedback Detail overlay (description, vote, comments)
// ---------------------------------------------------------------------------

function fhOpenFeedbackDetail(feedbackId) {
	fhKanbanActiveFeedbackId = feedbackId;
	var backdrop = document.getElementById("fh-feedback-modal-backdrop");
	document.getElementById("fh-feedback-form-section").style.display = "none";
	document.getElementById("fh-feedback-detail-section").style.display = "block";
	backdrop.className = "fh-modal-backdrop fh-visible";

	fhApiCall("feedback_hub.feedback.api.get_feedback", { feedback: feedbackId }, "GET").then(function (res) {
		if (!res.success) {
			fhToast(res.message, "error");
			backdrop.className = "fh-modal-backdrop";
			return;
		}
		fhRenderFeedbackDetail(res.data);
	});
}

function fhRenderFeedbackDetail(data) {
	document.getElementById("fh-feedback-detail-title").textContent = data.title;
	document.getElementById("fh-feedback-detail-meta").textContent =
		"Submitted by " + (data.reporter || (data.is_anonymous ? "Anonymous" : "Unknown")) + " on " + fhFormatDate(data.creation);
	document.getElementById("fh-feedback-detail-description").textContent = data.description || "";

	var voteBtn = document.getElementById("fh-feedback-detail-vote");
	voteBtn.classList.toggle("fh-voted", !!data.has_voted);
	document.getElementById("fh-feedback-detail-vote-count").textContent = data.vote_count;
	voteBtn.dataset.voted = data.has_voted ? "1" : "0";

	var thread = document.getElementById("fh-feedback-detail-comments");
	thread.innerHTML = "";
	(data.comments || []).forEach(function (comment) {
		thread.appendChild(fhRenderComment(comment));
	});
}

function fhRenderComment(comment) {
	var row = document.createElement("div");
	row.className = "fh-comment";

	var avatar = document.createElement("div");
	avatar.className = "fh-comment-avatar";
	avatar.textContent = (comment.commented_by || "?").charAt(0).toUpperCase();
	row.appendChild(avatar);

	var body = document.createElement("div");
	body.className = "fh-comment-body";

	var header = document.createElement("div");
	header.className = "fh-comment-header";
	var author = document.createElement("span");
	author.className = "fh-comment-author";
	author.textContent = comment.commented_by;
	var time = document.createElement("span");
	time.textContent = fhFormatDate(comment.creation);
	header.appendChild(author);
	header.appendChild(time);
	body.appendChild(header);

	var text = document.createElement("p");
	text.className = "fh-comment-text";
	text.textContent = comment.comment_text;
	body.appendChild(text);

	row.appendChild(body);
	return row;
}

function fhWireFeedbackDetail() {
	var closeBtn = document.getElementById("fh-feedback-detail-close");
	var backdrop = document.getElementById("fh-feedback-modal-backdrop");
	var voteBtn = document.getElementById("fh-feedback-detail-vote");
	var commentForm = document.getElementById("fh-feedback-comment-form");

	closeBtn.addEventListener("click", function () {
		backdrop.className = "fh-modal-backdrop";
	});

	voteBtn.addEventListener("click", function () {
		var wasVoted = voteBtn.dataset.voted === "1";
		var countEl = document.getElementById("fh-feedback-detail-vote-count");
		var previousCount = parseInt(countEl.textContent, 10) || 0;

		// Optimistic update, revert on failure (DesignSystem.md 6.1 / 5.5).
		voteBtn.dataset.voted = wasVoted ? "0" : "1";
		voteBtn.classList.toggle("fh-voted", !wasVoted);
		countEl.textContent = wasVoted ? previousCount - 1 : previousCount + 1;

		fhApiCall("feedback_hub.feedback.api.toggle_vote", { feedback: fhKanbanActiveFeedbackId }, "POST").then(
			function (res) {
				if (!res.success) {
					voteBtn.dataset.voted = wasVoted ? "1" : "0";
					voteBtn.classList.toggle("fh-voted", wasVoted);
					countEl.textContent = previousCount;
					fhToast(res.message, "error");
					return;
				}
				countEl.textContent = res.data.vote_count;
				var item = fhKanbanItems.find(function (i) {
					return i.name === fhKanbanActiveFeedbackId;
				});
				if (item) {
					item.vote_count = res.data.vote_count;
					fhRenderKanbanCards();
				}
			}
		);
	});

	commentForm.addEventListener("submit", function (e) {
		e.preventDefault();
		var textarea = document.getElementById("fh-feedback-comment-text");
		var text = textarea.value.trim();
		if (!text) return;

		fhApiCall(
			"feedback_hub.feedback.api.add_comment",
			{ feedback: fhKanbanActiveFeedbackId, comment_text: text },
			"POST"
		).then(function (res) {
			if (!res.success) {
				fhToast(res.message, "error");
				return;
			}
			textarea.value = "";
			document.getElementById("fh-feedback-detail-comments").appendChild(fhRenderComment(res.data));

			var item = fhKanbanItems.find(function (i) {
				return i.name === fhKanbanActiveFeedbackId;
			});
			if (item) {
				item.comment_count = (item.comment_count || 0) + 1;
				fhRenderKanbanCards();
			}
		});
	});
}

document.addEventListener("DOMContentLoaded", fhKanbanInit);
