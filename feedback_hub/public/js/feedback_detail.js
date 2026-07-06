document.addEventListener("DOMContentLoaded", function () {
	if (!window.fhFeedbackId) return;
	// Comments/attachments are fetched here rather than embedded server-side
	// via Jinja `tojson` - comment records include a raw `creation` datetime,
	// which plain `tojson` (unlike this app's JSON API responses, which go
	// through Frappe's own datetime-aware encoder) cannot serialize.
	fhApiCall("feedback_hub.feedback.api.get_feedback", { feedback: window.fhFeedbackId }, "GET").then(function (res) {
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}
		renderComments(res.data.comments || []);
		renderAttachments(res.data.attachments || []);
		renderActivityHistory(res.data.activity_history || []);
	});
	wireVoteButton();
	wireCommentForm();
	wireAttachmentUpload();
	wireDeleteButton();
});

function renderComments(comments) {
	var thread = document.getElementById("fh-comment-thread");
	thread.innerHTML = "";
	comments.forEach(function (comment) {
		thread.appendChild(renderComment(comment));
	});
}

function renderComment(comment) {
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

function renderActivityHistory(history) {
	var card = document.getElementById("fh-activity-history-card");
	var list = document.getElementById("fh-activity-history-list");
	if (!card || !list) return;
	if (!history.length) {
		card.style.display = "none";
		return;
	}
	card.style.display = "";
	list.innerHTML = "";
	history.forEach(function (entry) {
		var li = document.createElement("li");
		li.className = "fh-attachment-item";
		var summary = (entry.changes || [])
			.map(function (change) {
				return change.field + ": " + (change.from == null ? "-" : change.from) + " → " + (change.to == null ? "-" : change.to);
			})
			.join(", ") || "Updated";
		li.textContent = entry.by + " on " + fhFormatDate(entry.at) + " — " + summary;
		list.appendChild(li);
	});
}

function wireCommentForm() {
	var form = document.getElementById("fh-comment-form");
	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var textarea = document.getElementById("fh-comment-text");
		var text = textarea.value.trim();
		if (!text) return;

		fhApiCall(
			"feedback_hub.feedback.api.add_comment",
			{ feedback: window.fhFeedbackId, comment_text: text },
			"POST"
		).then(function (res) {
			if (!res.success) {
				fhToast(res.message, "error");
				return;
			}
			textarea.value = "";
			document.getElementById("fh-comment-thread").appendChild(renderComment(res.data));
		});
	});
}

function wireVoteButton() {
	var voteBtn = document.getElementById("fh-vote-btn");
	voteBtn.classList.toggle("fh-voted", voteBtn.dataset.voted === "1");

	voteBtn.addEventListener("click", function () {
		var wasVoted = voteBtn.dataset.voted === "1";
		var countEl = document.getElementById("fh-vote-count");
		var previousCount = parseInt(countEl.textContent, 10) || 0;

		voteBtn.dataset.voted = wasVoted ? "0" : "1";
		voteBtn.classList.toggle("fh-voted", !wasVoted);
		countEl.textContent = wasVoted ? previousCount - 1 : previousCount + 1;

		fhApiCall("feedback_hub.feedback.api.toggle_vote", { feedback: window.fhFeedbackId }, "POST").then(
			function (res) {
				if (!res.success) {
					voteBtn.dataset.voted = wasVoted ? "1" : "0";
					voteBtn.classList.toggle("fh-voted", wasVoted);
					countEl.textContent = previousCount;
					fhToast(res.message, "error");
					return;
				}
				countEl.textContent = res.data.vote_count;
			}
		);
	});
}

function renderAttachments(attachments) {
	var list = document.getElementById("fh-attachment-list");
	if (!list) return;
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

	if (window.fhCanUpdateFeedback) {
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
	}

	return li;
}

function wireAttachmentUpload() {
	var input = document.getElementById("fh-attachment-input");
	if (!input) return;

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

function wireDeleteButton() {
	var btn = document.getElementById("fh-delete-btn");
	if (!btn || !window.fhCanDeleteFeedback) return;

	btn.addEventListener("click", function () {
		fhConfirm(
			"Delete Feedback",
			"This will permanently delete this feedback item. This cannot be undone.",
			"Delete Feedback",
			function () {
				fhApiCall("feedback_hub.feedback.api.delete_feedback", { feedback: window.fhFeedbackId }, "POST").then(
					function (res) {
						if (res.success) {
							fhToast(res.message, "success");
							window.location.href = "/feedback_list";
						} else {
							fhToast(res.message, "error");
						}
					}
				);
			}
		);
	});
}
