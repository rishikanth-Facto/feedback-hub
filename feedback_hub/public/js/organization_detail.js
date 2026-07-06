document.addEventListener("DOMContentLoaded", function () {
	if (!window.fhOrgId) return;
	loadMembers();
	wireEditForm();
	wireLogoUpload();
	wireInviteForm();
	wireDeleteButton();
});

function wireLogoUpload() {
	var input = document.getElementById("fh-logo-input");
	if (!input) return;

	input.addEventListener("change", function () {
		var file = input.files[0];
		if (!file) return;

		fhUploadFile("feedback_hub.organization.api.upload_logo", file, { organization: window.fhOrgId }).then(
			function (res) {
				if (res.success) {
					var preview = document.getElementById("fh-logo-preview");
					preview.src = res.data.logo;
					preview.style.display = "";
					fhToast("Logo updated.", "success");
				} else {
					fhToast(res.message, "error");
				}
			}
		);
	});
}

function loadMembers() {
	var loading = document.getElementById("fh-members-loading");
	var table = document.getElementById("fh-members-table");
	var tbody = document.getElementById("fh-members-table-body");

	fhApiCall("feedback_hub.organization.api.list_members", { organization: window.fhOrgId }, "GET").then(function (res) {
		loading.style.display = "none";
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}

		tbody.innerHTML = "";
		(res.data.members || []).forEach(function (member) {
			tbody.appendChild(renderMemberRow(member));
		});
		table.style.display = "table";
	});
}

function renderMemberRow(member) {
	var tr = document.createElement("tr");

	var nameTd = document.createElement("td");
	nameTd.textContent = member.user || member.invited_email || "-";
	tr.appendChild(nameTd);

	var roleTd = document.createElement("td");
	if (window.fhIsAdmin) {
		var select = document.createElement("select");
		["Organization Admin", "Product Owner", "Moderator", "Developer", "Customer"].forEach(function (role) {
			var option = document.createElement("option");
			option.value = role;
			option.textContent = role;
			option.selected = role === member.role;
			select.appendChild(option);
		});
		select.addEventListener("change", function () {
			fhApiCall("feedback_hub.organization.api.update_member", { member: member.name, role: select.value }).then(
				function (res) {
					if (res.success) {
						fhToast("Role updated.", "success");
					} else {
						fhToast(res.message, "error");
						select.value = member.role;
					}
				}
			);
		});
		roleTd.appendChild(select);
	} else {
		roleTd.textContent = member.role;
	}
	tr.appendChild(roleTd);

	var statusTd = document.createElement("td");
	var badge = document.createElement("span");
	badge.className = fhStatusBadgeClass(member.status);
	badge.textContent = member.status;
	statusTd.appendChild(badge);
	tr.appendChild(statusTd);

	var joinedTd = document.createElement("td");
	joinedTd.textContent = fhFormatDate(member.joined_on);
	tr.appendChild(joinedTd);

	var actionsTd = document.createElement("td");
	actionsTd.className = "fh-table-actions";
	if (window.fhIsAdmin) {
		var removeBtn = document.createElement("button");
		removeBtn.type = "button";
		removeBtn.className = "fh-btn fh-btn-secondary";
		removeBtn.textContent = "Remove";
		removeBtn.addEventListener("click", function () {
			fhConfirm(
				"Remove Member",
				"Remove " + (member.user || member.invited_email) + " from this organization?",
				"Remove Member",
				function () {
					fhApiCall("feedback_hub.organization.api.remove_member", { member: member.name }, "POST").then(
						function (res) {
							if (res.success) {
								fhToast("Member removed.", "success");
								loadMembers();
							} else {
								fhToast(res.message, "error");
							}
						}
					);
				}
			);
		});
		actionsTd.appendChild(removeBtn);
	}
	tr.appendChild(actionsTd);

	return tr;
}

function wireEditForm() {
	var form = document.getElementById("fh-org-edit-form");
	if (!form || !window.fhIsAdmin) return;

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var alertEl = document.getElementById("fh-alert");
		fhHideAlert(alertEl);

		fhApiCall("feedback_hub.organization.api.update_organization", {
			organization: window.fhOrgId,
			organization_name: document.getElementById("organization_name").value.trim(),
			description: document.getElementById("description").value.trim(),
		}).then(function (res) {
			if (res.success) {
				fhToast("Organization updated.", "success");
			} else {
				fhShowAlert(alertEl, res.message, "error");
			}
		});
	});
}

function wireInviteForm() {
	var form = document.getElementById("fh-invite-form");
	if (!form) return;

	form.addEventListener("submit", function (e) {
		e.preventDefault();
		var alertEl = document.getElementById("fh-invite-alert");
		var submitBtn = document.getElementById("fh-invite-submit");
		fhHideAlert(alertEl);
		submitBtn.disabled = true;

		fhApiCall("feedback_hub.organization.api.invite_member", {
			organization: window.fhOrgId,
			email: document.getElementById("invite_email").value.trim(),
			role: document.getElementById("invite_role").value,
		}).then(function (res) {
			submitBtn.disabled = false;
			if (res.success) {
				fhToast("Invitation sent.", "success");
				form.reset();
				loadMembers();
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
			"Delete Organization",
			"This will deactivate the organization. This cannot be undone from here.",
			"Delete Organization",
			function () {
				deleteOrganization(false);
			}
		);
	});
}

function deleteOrganization(force) {
	fhApiCall(
		"feedback_hub.organization.api.delete_organization",
		{ organization: window.fhOrgId, force: force ? 1 : 0 },
		"POST"
	).then(function (res) {
		if (res.success) {
			fhToast(res.message, "success");
			window.location.href = "/organizations";
			return;
		}

		if (!force) {
			// Blocked by active members - offer force delete (spec: organization-ui
			// "Delete blocked by active members surfaced").
			fhConfirm(
				"Force Delete Organization",
				res.message + " Force delete will remove the organization and all its members permanently.",
				"Force Delete Organization",
				function () {
					deleteOrganization(true);
				}
			);
		} else {
			fhToast(res.message, "error");
		}
	});
}
