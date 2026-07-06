document.addEventListener("DOMContentLoaded", function () {
	populateBoardSelect();
	populateCategorySelect();
});

function populateBoardSelect() {
	fhApiCall("feedback_hub.product.api.list_boards", {}, "GET").then(function (res) {
		var select = document.getElementById("board");
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}
		(res.data.boards || []).forEach(function (board) {
			var option = document.createElement("option");
			option.value = board.name;
			option.textContent = board.board_name;
			if (window.fhPreselectedBoard && board.name === window.fhPreselectedBoard) option.selected = true;
			select.appendChild(option);
		});
	});
}

function populateCategorySelect() {
	fhFetchCategories().then(function (categories) {
		var select = document.getElementById("category");
		categories.forEach(function (category) {
			var option = document.createElement("option");
			option.value = category.name;
			option.textContent = category.category_name;
			select.appendChild(option);
		});
	});
}

document.getElementById("fh-feedback-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var board = document.getElementById("board").value;
	var title = document.getElementById("title").value.trim();
	var description = document.getElementById("description").value.trim();
	var category = document.getElementById("category").value;
	var priority = document.getElementById("priority").value;
	var isAnonymous = document.getElementById("is_anonymous").checked;
	var files = document.getElementById("attachments").files;

	submitBtn.disabled = true;
	submitBtn.textContent = "Submitting...";

	fhApiCall("feedback_hub.feedback.api.create_feedback", {
		board: board,
		title: title,
		description: description,
		category: category,
		priority: priority,
		is_anonymous: isAnonymous ? 1 : 0,
	}).then(function (res) {
		if (!res.success) {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Submit Feedback";
			return;
		}

		var feedbackId = res.data.name;
		uploadAttachments(feedbackId, files).then(function () {
			window.location.href = "/feedback_detail?id=" + encodeURIComponent(feedbackId);
		});
	});
});

function uploadAttachments(feedbackId, files) {
	var uploads = [];
	for (var i = 0; i < files.length; i++) {
		uploads.push(
			fhUploadFile("feedback_hub.feedback.api.add_attachment", files[i], { feedback: feedbackId }).then(
				function (res) {
					if (!res.success) fhToast(res.message, "error");
				}
			)
		);
	}
	return Promise.all(uploads);
}
