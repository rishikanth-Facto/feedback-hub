document.addEventListener("DOMContentLoaded", function () {
	populateCategorySelect();
	renderAttachments(window.fhInitialAttachments || []);
	wireAttachmentUpload();
});

function populateCategorySelect() {
	fhFetchCategories().then(function (categories) {
		var select = document.getElementById("category");
		categories.forEach(function (category) {
			var option = document.createElement("option");
			option.value = category.name;
			option.textContent = category.category_name;
			if (category.name === window.fhCurrentCategory) option.selected = true;
			select.appendChild(option);
		});
	});
}

document.getElementById("fh-feedback-edit-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	submitBtn.disabled = true;
	submitBtn.textContent = "Saving...";

	fhApiCall("feedback_hub.feedback.api.update_feedback", {
		feedback: window.fhFeedbackId,
		title: document.getElementById("title").value.trim(),
		description: document.getElementById("description").value.trim(),
		category: document.getElementById("category").value,
		priority: document.getElementById("priority").value,
		is_anonymous: document.getElementById("is_anonymous").checked ? 1 : 0,
	}).then(function (res) {
		if (res.success) {
			window.location.href = "/feedback_detail?id=" + encodeURIComponent(window.fhFeedbackId);
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Save Changes";
		}
	});
});

function renderAttachments(attachments) {
	var list = document.getElementById("fh-attachment-list");
	list.innerHTML = "";
	attachments.forEach(function (attachment) {
		list.appendChild(renderAttachmentRow(attachment));
	});
}

function renderAttachmentRow(attachment) {
	var li = document.createElement("li");
	li.className = "fh-attachment-item";
	li.dataset.rowName = attachment.name;

	var link = document.createElement("a");
	link.href = attachment.file_url;
	link.target = "_blank";
	link.rel = "noopener";
	link.textContent = attachment.file_name + " (" + Math.ceil(attachment.file_size / 1024) + " KB)";
	li.appendChild(link);

	var removeBtn = document.createElement("button");
	removeBtn.type = "button";
	removeBtn.className = "fh-btn fh-btn-secondary";
	removeBtn.textContent = "Remove";
	removeBtn.addEventListener("click", function () {
		fhApiCall(
			"feedback_hub.feedback.api.remove_attachment",
			{ feedback: window.fhFeedbackId, attachment: attachment.name },
			"POST"
		).then(function (res) {
			if (!res.success) {
				fhToast(res.message, "error");
				return;
			}
			li.remove();
			fhToast("Attachment removed.", "success");
		});
	});
	li.appendChild(removeBtn);

	return li;
}

function wireAttachmentUpload() {
	var input = document.getElementById("fh-attachment-input");
	input.addEventListener("change", function () {
		var file = input.files[0];
		if (!file) return;

		fhUploadFile("feedback_hub.feedback.api.add_attachment", file, { feedback: window.fhFeedbackId }).then(
			function (res) {
				input.value = "";
				if (!res.success) {
					fhToast(res.message, "error");
					return;
				}
				document.getElementById("fh-attachment-list").appendChild(renderAttachmentRow(res.data));
				fhToast("Attachment added.", "success");
			}
		);
	});
}
