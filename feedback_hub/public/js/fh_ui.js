// Feedback Hub - shared confirmation-modal and toast helpers (org-management
// UI pages), built once so every page triggers them consistently instead of
// re-implementing the same markup/logic per page (DesignSystem.md 5.12/5.13).

function fhConfirm(title, body, confirmLabel, onConfirm, danger) {
	var backdrop = document.getElementById("fh-modal-backdrop");
	if (!backdrop) return;
	document.getElementById("fh-modal-title").textContent = title;
	document.getElementById("fh-modal-body").textContent = body;

	var confirmBtn = document.getElementById("fh-modal-confirm");
	confirmBtn.textContent = confirmLabel;
	confirmBtn.className = "fh-btn " + (danger === false ? "fh-btn-primary" : "fh-btn-danger");

	var newConfirmBtn = confirmBtn.cloneNode(true);
	confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
	newConfirmBtn.addEventListener("click", function () {
		fhCloseModal();
		onConfirm();
	});

	backdrop.className = "fh-modal-backdrop fh-visible";
}

function fhCloseModal() {
	var backdrop = document.getElementById("fh-modal-backdrop");
	if (backdrop) backdrop.className = "fh-modal-backdrop";
}

document.addEventListener("keydown", function (e) {
	if (e.key === "Escape") fhCloseModal();
});
document.addEventListener("DOMContentLoaded", function () {
	var cancelBtn = document.getElementById("fh-modal-cancel");
	if (cancelBtn) cancelBtn.addEventListener("click", fhCloseModal);
	var backdrop = document.getElementById("fh-modal-backdrop");
	if (backdrop) {
		backdrop.addEventListener("click", function (e) {
			if (e.target === backdrop) fhCloseModal();
		});
	}
});

// Frappe datetimes come back as "YYYY-MM-DD HH:MM:SS.ffffff" - trim to the
// minute so table cells stay single-line instead of wrapping onto two rows.
function fhFormatDate(value) {
	if (!value) return "-";
	return value.slice(0, 16);
}

var FH_STATUS_BADGE_CLASS = {
	Active: "fh-badge-active",
	Pending: "fh-badge-pending",
	Suspended: "fh-badge-suspended",
	Inactive: "fh-badge-inactive",
	// Product status (Module 3) - "archived" maps to the Muted/Draft state
	// per DesignSystem.md 5.3, not a new color.
	Archived: "fh-badge-archived",
	// Board visibility (Module 3) - reuses the same badge mechanism rather
	// than a parallel component (design.md Decision 13).
	Public: "fh-badge-public",
	Private: "fh-badge-private",
	Internal: "fh-badge-internal",
	// Feedback priority (feedback-management) and feedback status - same
	// badge mechanism, additive-only entries.
	Low: "fh-badge-low",
	Medium: "fh-badge-medium",
	High: "fh-badge-high",
	Urgent: "fh-badge-urgent",
	New: "fh-badge-new",
	"Under Review": "fh-badge-under-review",
	Approved: "fh-badge-approved",
	Rejected: "fh-badge-rejected",
	Planned: "fh-badge-planned",
	"In Progress": "fh-badge-in-progress",
	Released: "fh-badge-released",
	Closed: "fh-badge-closed",
};

function fhStatusBadgeClass(status) {
	return "fh-badge " + (FH_STATUS_BADGE_CLASS[status] || "");
}

var FH_MAX_TOASTS = 4;

function fhToast(message, variant) {
	var stack = document.getElementById("fh-toast-stack");
	if (!stack) return;

	variant = variant || "info";
	var toast = document.createElement("div");
	toast.className = "fh-toast fh-toast-" + variant;

	var text = document.createElement("span");
	text.textContent = message;
	toast.appendChild(text);

	var close = document.createElement("button");
	close.className = "fh-toast-close";
	close.setAttribute("aria-label", "Dismiss");
	close.textContent = "×";
	close.addEventListener("click", function () {
		toast.remove();
	});
	toast.appendChild(close);

	stack.appendChild(toast);
	while (stack.children.length > FH_MAX_TOASTS) {
		stack.removeChild(stack.firstChild);
	}

	if (variant === "success" || variant === "info") {
		setTimeout(function () {
			toast.remove();
		}, 4000);
	}
}
