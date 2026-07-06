// Feedback Hub - organization switcher, injected via templates/includes/navbar.html
// on every authenticated page (Section 16: hidden/disabled when the caller
// has 0-1 memberships, since there's nothing to switch between).
document.addEventListener("DOMContentLoaded", function () {
	var wrapper = document.getElementById("fh-org-switcher");
	var select = document.getElementById("fh-org-switcher-select");
	if (!wrapper || !select) return;

	Promise.all([
		fhApiCall("feedback_hub.organization.api.list_organizations", {}, "GET"),
		fhApiCall("feedback_hub.organization.api.get_active_organization", {}, "GET"),
	]).then(function (results) {
		var listRes = results[0];
		var activeRes = results[1];
		if (!listRes.success) return;

		var organizations = listRes.data.organizations || [];
		if (organizations.length < 2) return;

		var activeOrg = activeRes.success ? activeRes.data.organization : null;

		if (!activeOrg) {
			// No organization is actually active server-side yet (this happens
			// whenever a caller belongs to 2+ organizations and has never
			// explicitly switched this session - get_active_organization only
			// auto-resolves when there's exactly one membership). Without this
			// placeholder, the <select> silently renders its first real <option>
			// as if chosen, which looks identical to an actual active
			// organization but every org-scoped page (Products, Boards,
			// Feedback...) still sees no active organization and behaves as if
			// nothing exists - a confusing, silent mismatch. Forcing a visible
			// placeholder makes the "you must pick one" state honest.
			var placeholder = document.createElement("option");
			placeholder.value = "";
			placeholder.textContent = "Select Organization";
			placeholder.disabled = true;
			placeholder.selected = true;
			select.appendChild(placeholder);
		}

		organizations.forEach(function (org) {
			var option = document.createElement("option");
			option.value = org.name;
			option.textContent = org.organization_name;
			if (org.name === activeOrg) option.selected = true;
			select.appendChild(option);
		});

		wrapper.style.display = "inline-flex";

		select.addEventListener("change", function () {
			fhApiCall("feedback_hub.organization.api.switch_organization", { organization: select.value }).then(
				function (res) {
					if (res.success) {
						window.location.reload();
					} else {
						fhToast(res.message, "error");
					}
				}
			);
		});
	});
});
