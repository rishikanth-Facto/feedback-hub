document.getElementById("fh-org-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var organizationName = document.getElementById("organization_name").value.trim();
	var description = document.getElementById("description").value.trim();

	submitBtn.disabled = true;
	submitBtn.textContent = "Creating...";

	fhApiCall("feedback_hub.organization.api.create_organization", {
		organization_name: organizationName,
		description: description,
	}).then(function (res) {
		if (res.success) {
			window.location.href = "/organization_detail?id=" + encodeURIComponent(res.data.name);
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Create Organization";
		}
	});
});
