document.addEventListener("DOMContentLoaded", function () {
	if (!window.fhProductId) return;
	loadBoards();
	wireEditForm();
	wireDeleteButton();
});

function loadBoards() {
	var loading = document.getElementById("fh-boards-loading");
	var table = document.getElementById("fh-boards-table");
	var tbody = document.getElementById("fh-boards-table-body");
	var empty = document.getElementById("fh-boards-empty");

	fhApiCall("feedback_hub.product.api.list_boards", { product: window.fhProductId }, "GET").then(function (res) {
		loading.style.display = "none";
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}

		var boards = res.data.boards || [];
		if (!boards.length) {
			empty.style.display = "block";
			return;
		}

		tbody.innerHTML = "";
		boards.forEach(function (board) {
			tbody.appendChild(renderBoardRow(board));
		});
		table.style.display = "table";
	});
}

function renderBoardRow(board) {
	var tr = document.createElement("tr");

	var nameTd = document.createElement("td");
	var link = document.createElement("a");
	link.href = "/board_detail?id=" + encodeURIComponent(board.name);
	link.textContent = board.board_name;
	nameTd.appendChild(link);
	tr.appendChild(nameTd);

	var slugTd = document.createElement("td");
	slugTd.className = "fh-mono";
	slugTd.textContent = board.slug;
	tr.appendChild(slugTd);

	var visibilityTd = document.createElement("td");
	var badge = document.createElement("span");
	badge.className = fhStatusBadgeClass(board.visibility);
	badge.textContent = board.visibility;
	visibilityTd.appendChild(badge);
	tr.appendChild(visibilityTd);

	var actionsTd = document.createElement("td");
	actionsTd.className = "fh-table-actions";
	var viewLink = document.createElement("a");
	viewLink.href = "/board_detail?id=" + encodeURIComponent(board.name);
	viewLink.className = "fh-btn fh-btn-secondary";
	viewLink.textContent = "View";
	actionsTd.appendChild(viewLink);
	tr.appendChild(actionsTd);

	return tr;
}

function wireEditForm() {
	var form = document.getElementById("fh-product-edit-form");
	if (!form) return;

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var alertEl = document.getElementById("fh-alert");
		fhHideAlert(alertEl);

		fhApiCall("feedback_hub.product.api.update_product", {
			product: window.fhProductId,
			product_name: document.getElementById("product_name").value.trim(),
			description: document.getElementById("description").value.trim(),
			status: document.getElementById("status").value,
		}).then(function (res) {
			if (res.success) {
				fhToast("Product updated.", "success");
			} else {
				fhShowAlert(alertEl, res.message, "error");
			}
		});
	});
}

function wireDeleteButton() {
	var btn = document.getElementById("fh-delete-btn");
	if (!btn) return;

	btn.addEventListener("click", function () {
		fhConfirm(
			"Delete Product",
			"This will permanently delete this product. This cannot be undone.",
			"Delete Product",
			function () {
				deleteProduct(false);
			}
		);
	});
}

function deleteProduct(force) {
	fhApiCall(
		"feedback_hub.product.api.delete_product",
		{ product: window.fhProductId, force: force ? 1 : 0 },
		"POST"
	).then(function (res) {
		if (res.success) {
			fhToast(res.message, "success");
			window.location.href = "/products";
			return;
		}

		if (!force) {
			// Blocked by existing boards - offer force delete (spec:
			// product-board-ui "Delete blocked by existing boards surfaced").
			fhConfirm(
				"Force Delete Product",
				res.message + " Force delete will remove the product and all its boards permanently.",
				"Force Delete Product",
				function () {
					deleteProduct(true);
				}
			);
		} else {
			fhToast(res.message, "error");
		}
	});
}
