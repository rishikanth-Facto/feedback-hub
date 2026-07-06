// Feedback Hub - product-grouped Kanban view for the Feedback List page.
// Distinct from fh_kanban.js (board_detail.html's single-Board Kanban, left
// untouched per design.md's Non-Goals) - this one is keyed by Product,
// aggregating every Board under it into one set of columns, and reuses
// feedback_list.html/feedback_detail.html for create/detail instead of an
// inline modal (that page pair already exists here, unlike board_detail.html).

// "New"/"Approved"/"Rejected"/"Closed" are deliberately not columns here -
// same reasoning and same list as fh_kanban.js (design.md Decision 19).
var FH_FEEDBACK_KANBAN_STATUSES = ["Under Review", "Planned", "In Progress", "Released"];
var fhFeedbackKanbanItems = [];
var fhFeedbackKanbanProduct = "";

document.addEventListener("DOMContentLoaded", function () {
	var listToggle = document.getElementById("fh-view-toggle-list");
	var kanbanToggle = document.getElementById("fh-view-toggle-kanban");
	var listView = document.getElementById("fh-feedback-list-view");
	var kanbanView = document.getElementById("fh-feedback-kanban-view");
	var productSelect = document.getElementById("fh-kanban-product-select");
	if (!listToggle || !kanbanToggle || !productSelect) return;

	listToggle.addEventListener("click", function () {
		listToggle.className = "fh-btn fh-btn-primary";
		kanbanToggle.className = "fh-btn fh-btn-secondary";
		listView.style.display = "block";
		kanbanView.style.display = "none";
	});

	kanbanToggle.addEventListener("click", function () {
		kanbanToggle.className = "fh-btn fh-btn-primary";
		listToggle.className = "fh-btn fh-btn-secondary";
		listView.style.display = "none";
		kanbanView.style.display = "block";
	});

	fhRenderFeedbackKanbanShell();

	fhApiCall("feedback_hub.product.api.list_visible_products", {}, "GET").then(function (res) {
		if (!res.success) return;
		(res.data.products || []).forEach(function (product) {
			var option = document.createElement("option");
			option.value = product.name;
			option.textContent = product.product_name;
			productSelect.appendChild(option);
		});
	});

	productSelect.addEventListener("change", function () {
		fhFeedbackKanbanProduct = productSelect.value;
		var boardWrap = document.getElementById("fh-feedback-kanban-board-wrap");
		var noProduct = document.getElementById("fh-kanban-no-product");
		if (!fhFeedbackKanbanProduct) {
			boardWrap.style.display = "none";
			noProduct.style.display = "block";
			return;
		}
		noProduct.style.display = "none";
		boardWrap.style.display = "block";
		fhLoadFeedbackKanban();
	});
});

function fhRenderFeedbackKanbanShell() {
	var tabs = document.getElementById("fh-feedback-kanban-tabs");
	var board = document.getElementById("fh-feedback-kanban-board");
	tabs.innerHTML = "";
	board.innerHTML = "";

	FH_FEEDBACK_KANBAN_STATUSES.forEach(function (status, index) {
		var tabBtn = document.createElement("button");
		tabBtn.type = "button";
		tabBtn.textContent = status;
		tabBtn.className = index === 0 ? "active" : "";
		tabBtn.addEventListener("click", function () {
			fhSetFeedbackKanbanMobileColumn(status);
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
		count.id = "fh-feedback-kanban-count-" + fhFeedbackKanbanSlug(status);
		header.appendChild(name);
		header.appendChild(count);
		column.appendChild(header);

		var cards = document.createElement("div");
		cards.className = "fh-kanban-cards";
		cards.id = "fh-feedback-kanban-cards-" + fhFeedbackKanbanSlug(status);
		column.appendChild(cards);

		fhWireFeedbackKanbanDropTarget(column, cards);
		board.appendChild(column);
	});
}

function fhFeedbackKanbanSlug(status) {
	return status.toLowerCase().replace(/\s+/g, "-");
}

function fhSetFeedbackKanbanMobileColumn(status) {
	document.querySelectorAll("#fh-feedback-kanban-tabs button").forEach(function (btn) {
		btn.classList.toggle("active", btn.textContent === status);
	});
	document.querySelectorAll("#fh-feedback-kanban-board .fh-kanban-column").forEach(function (col) {
		col.classList.toggle("fh-mobile-active", col.dataset.status === status);
	});
}

function fhLoadFeedbackKanban() {
	// order_by/order_dir/page_size: 0 match fh_kanban.js's board Kanban -
	// oldest-first, every item unpaginated, not the Feedback List page's own
	// paginated defaults.
	fhApiCall(
		"feedback_hub.feedback.api.list_feedback",
		{ product: fhFeedbackKanbanProduct, order_by: "creation", order_dir: "asc", page_size: 0 },
		"GET"
	).then(function (res) {
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}
		fhFeedbackKanbanItems = res.data.feedback || [];
		fhRenderFeedbackKanbanCards();
	});
}

function fhRenderFeedbackKanbanCards() {
	FH_FEEDBACK_KANBAN_STATUSES.forEach(function (status) {
		var container = document.getElementById("fh-feedback-kanban-cards-" + fhFeedbackKanbanSlug(status));
		container.innerHTML = "";
		var items = fhFeedbackKanbanItems.filter(function (item) {
			return item.status === status;
		});
		items.forEach(function (item) {
			container.appendChild(fhRenderFeedbackKanbanCard(item));
		});
		document.getElementById("fh-feedback-kanban-count-" + fhFeedbackKanbanSlug(status)).textContent = items.length;
	});
}

function fhRenderFeedbackKanbanCard(item) {
	var card = document.createElement("div");
	card.className = "fh-kanban-card" + (window.fhCanMoveFeedback ? " fh-draggable" : "");
	card.dataset.feedbackId = item.name;
	card.draggable = !!window.fhCanMoveFeedback;

	var title = document.createElement("p");
	title.className = "fh-kanban-card-title";
	title.textContent = item.title;
	card.appendChild(title);

	var boardLine = document.createElement("p");
	boardLine.className = "fh-hint";
	boardLine.textContent = item.board;
	card.appendChild(boardLine);

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
		window.location.href = "/feedback_detail?id=" + encodeURIComponent(item.name);
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

function fhWireFeedbackKanbanDropTarget(column, cards) {
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
		fhMoveFeedbackKanbanStatus(feedbackId, column.dataset.status);
	});
}

function fhMoveFeedbackKanbanStatus(feedbackId, newStatus) {
	var item = fhFeedbackKanbanItems.find(function (i) {
		return i.name === feedbackId;
	});
	if (!item || item.status === newStatus) return;

	var previousStatus = item.status;
	item.status = newStatus; // optimistic update
	fhRenderFeedbackKanbanCards();

	fhApiCall("feedback_hub.feedback.api.move_status", { feedback: feedbackId, status: newStatus }, "POST").then(
		function (res) {
			if (!res.success) {
				item.status = previousStatus; // rollback
				fhRenderFeedbackKanbanCards();
				fhToast(res.message, "error");
			}
		}
	);
}
