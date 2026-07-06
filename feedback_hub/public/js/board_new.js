document.getElementById("fh-board-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var boardName = document.getElementById("board_name").value.trim();
	var visibility = document.getElementById("visibility").value;
	var description = document.getElementById("description").value.trim();

	submitBtn.disabled = true;
	submitBtn.textContent = "Creating...";

	fhApiCall("feedback_hub.product.api.create_board", {
		product: window.fhBoardProductId,
		board_name: boardName,
		visibility: visibility,
		description: description,
	}).then(function (res) {
		if (res.success) {
			window.location.href = "/board_detail?id=" + encodeURIComponent(res.data.name);
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Create Board";
		}
	});
});
