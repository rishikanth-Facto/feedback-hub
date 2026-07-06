document.addEventListener("DOMContentLoaded", function () {
	if (!window.fhBoardId) return;
	wireSettingsModal();
	wireEditForm();
	wireDeleteButton();
});

function wireSettingsModal() {
	var openBtn = document.getElementById("fh-board-settings-btn");
	var closeBtn = document.getElementById("fh-board-settings-close");
	var backdrop = document.getElementById("fh-board-settings-backdrop");
	if (!openBtn || !backdrop) return;

	openBtn.addEventListener("click", function () {
		backdrop.className = "fh-modal-backdrop fh-visible";
	});
	closeBtn.addEventListener("click", function () {
		backdrop.className = "fh-modal-backdrop";
	});
	backdrop.addEventListener("click", function (e) {
		if (e.target === backdrop) backdrop.className = "fh-modal-backdrop";
	});
}

function wireEditForm() {
	var form = document.getElementById("fh-board-edit-form");
	if (!form || !window.fhCanUpdateBoard) return;

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var alertEl = document.getElementById("fh-alert");
		fhHideAlert(alertEl);

		fhApiCall("feedback_hub.product.api.update_board", {
			board: window.fhBoardId,
			board_name: document.getElementById("board_name").value.trim(),
			visibility: document.getElementById("visibility").value,
			description: document.getElementById("description").value.trim(),
		}).then(function (res) {
			if (res.success) {
				fhToast("Board updated.", "success");
			} else {
				fhShowAlert(alertEl, res.message, "error");
			}
		});
	});
}

function wireDeleteButton() {
	var btn = document.getElementById("fh-delete-btn");
	if (!btn || !window.fhCanDeleteBoard) return;

	btn.addEventListener("click", function () {
		fhConfirm(
			"Delete Board",
			"This will permanently delete this board. This cannot be undone.",
			"Delete Board",
			function () {
				fhApiCall("feedback_hub.product.api.delete_board", { board: window.fhBoardId }, "POST").then(
					function (res) {
						if (res.success) {
							fhToast(res.message, "success");
							window.location.href = "/products";
						} else {
							fhToast(res.message, "error");
						}
					}
				);
			}
		);
	});
}
