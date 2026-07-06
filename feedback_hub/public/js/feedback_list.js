document.addEventListener("DOMContentLoaded", function () {
	var loading = document.getElementById("fh-feedback-list-loading");
	var table = document.getElementById("fh-feedback-table");
	var tbody = document.getElementById("fh-feedback-table-body");
	var empty = document.getElementById("fh-feedback-empty");
	var pagination = document.getElementById("fh-feedback-pagination");
	var paginationInfo = document.getElementById("fh-feedback-pagination-info");
	var prevBtn = document.getElementById("fh-feedback-prev-page");
	var nextBtn = document.getElementById("fh-feedback-next-page");
	var filterForm = document.getElementById("fh-feedback-filter-bar");

	var PAGE_SIZE = 20;
	var state = { page: 1 };

	populateBoardFilter();
	populateCategoryFilter();
	loadFeedback();

	filterForm.addEventListener("submit", function (e) {
		e.preventDefault();
		state.page = 1;
		loadFeedback();
	});

	prevBtn.addEventListener("click", function () {
		if (state.page > 1) {
			state.page -= 1;
			loadFeedback();
		}
	});

	nextBtn.addEventListener("click", function () {
		state.page += 1;
		loadFeedback();
	});

	function populateBoardFilter() {
		fhApiCall("feedback_hub.product.api.list_boards", {}, "GET").then(function (res) {
			if (!res.success) return;
			var select = document.getElementById("filter_board");
			(res.data.boards || []).forEach(function (board) {
				var option = document.createElement("option");
				option.value = board.name;
				option.textContent = board.board_name;
				select.appendChild(option);
			});
		});
	}

	function populateCategoryFilter() {
		fhFetchCategories().then(function (categories) {
			var select = document.getElementById("filter_category");
			categories.forEach(function (category) {
				var option = document.createElement("option");
				option.value = category.name;
				option.textContent = category.category_name;
				select.appendChild(option);
			});
		});
	}

	function loadFeedback() {
		loading.style.display = "block";
		table.style.display = "none";
		empty.style.display = "none";
		pagination.style.display = "none";

		// Built up rather than passing `undefined` for unset filters -
		// URLSearchParams stringifies `undefined` to the literal text
		// "undefined" instead of dropping the key, which would otherwise be
		// sent to the API as a real (bogus) filter value.
		var args = {
			order_by: document.getElementById("filter_sort").value,
			order_dir: document.getElementById("filter_sort_dir").value,
			page: state.page,
			page_size: PAGE_SIZE,
		};
		[
			["board", document.getElementById("filter_board").value],
			["category", document.getElementById("filter_category").value],
			["priority", document.getElementById("filter_priority").value],
			["status", document.getElementById("filter_status").value],
			["search", document.getElementById("filter_search").value.trim()],
		].forEach(function (pair) {
			if (pair[1]) args[pair[0]] = pair[1];
		});

		fhApiCall("feedback_hub.feedback.api.list_feedback", args, "GET").then(function (res) {
			loading.style.display = "none";
			if (!res.success) {
				fhToast(res.message, "error");
				return;
			}

			var items = res.data.feedback || [];
			if (!items.length) {
				empty.style.display = "block";
				return;
			}

			tbody.innerHTML = "";
			items.forEach(function (item) {
				tbody.appendChild(renderRow(item));
			});
			table.style.display = "table";

			renderPagination(res.data.total, res.data.page, res.data.page_size);
		});
	}

	function renderRow(item) {
		var tr = document.createElement("tr");

		var titleTd = document.createElement("td");
		var link = document.createElement("a");
		link.href = "/feedback_detail?id=" + encodeURIComponent(item.name);
		link.textContent = item.title;
		titleTd.appendChild(link);
		tr.appendChild(titleTd);

		appendTextCell(tr, item.board);
		appendTextCell(tr, item.category);

		var priorityTd = document.createElement("td");
		var priorityBadge = document.createElement("span");
		priorityBadge.className = fhStatusBadgeClass(item.priority);
		priorityBadge.textContent = item.priority;
		priorityTd.appendChild(priorityBadge);
		tr.appendChild(priorityTd);

		var statusTd = document.createElement("td");
		var statusBadge = document.createElement("span");
		statusBadge.className = fhStatusBadgeClass(item.status);
		statusBadge.textContent = item.status;
		statusTd.appendChild(statusBadge);
		tr.appendChild(statusTd);

		appendTextCell(tr, item.is_anonymous ? ("Anonymous" + (item.reporter ? " (" + item.reporter + ")" : "")) : item.reporter || "-");

		var votesTd = document.createElement("td");
		votesTd.textContent = item.vote_count;
		tr.appendChild(votesTd);

		var actionsTd = document.createElement("td");
		actionsTd.className = "fh-table-actions";
		var viewLink = document.createElement("a");
		viewLink.href = "/feedback_detail?id=" + encodeURIComponent(item.name);
		viewLink.className = "fh-btn fh-btn-secondary";
		viewLink.textContent = "View";
		actionsTd.appendChild(viewLink);
		tr.appendChild(actionsTd);

		return tr;
	}

	function appendTextCell(tr, text) {
		var td = document.createElement("td");
		td.textContent = text || "-";
		tr.appendChild(td);
	}

	function renderPagination(total, page, pageSize) {
		var totalPages = Math.max(1, Math.ceil(total / pageSize));
		paginationInfo.textContent = "Page " + page + " of " + totalPages + " (" + total + " total)";
		prevBtn.disabled = page <= 1;
		nextBtn.disabled = page >= totalPages;
		pagination.style.display = "flex";
	}
});
