document.addEventListener("DOMContentLoaded", function () {
	var loading = document.getElementById("fh-org-list-loading");
	var table = document.getElementById("fh-org-table");
	var tbody = document.getElementById("fh-org-table-body");
	var empty = document.getElementById("fh-org-empty");

	fhApiCall("feedback_hub.organization.api.list_organizations", {}, "GET").then(function (res) {
		loading.style.display = "none";
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}

		var organizations = res.data.organizations || [];
		if (!organizations.length) {
			empty.style.display = "block";
			return;
		}

		organizations.forEach(function (org) {
			var tr = document.createElement("tr");

			var nameTd = document.createElement("td");
			var link = document.createElement("a");
			link.href = "/organization_detail?id=" + encodeURIComponent(org.name);
			link.textContent = org.organization_name;
			nameTd.appendChild(link);
			tr.appendChild(nameTd);

			var slugTd = document.createElement("td");
			slugTd.className = "fh-mono";
			slugTd.textContent = org.slug;
			tr.appendChild(slugTd);

			var roleTd = document.createElement("td");
			roleTd.textContent = org.role;
			tr.appendChild(roleTd);

			var statusTd = document.createElement("td");
			var badge = document.createElement("span");
			badge.className = fhStatusBadgeClass(org.status);
			badge.textContent = org.status;
			statusTd.appendChild(badge);
			tr.appendChild(statusTd);

			var actionsTd = document.createElement("td");
			actionsTd.className = "fh-table-actions";
			var viewLink = document.createElement("a");
			viewLink.href = "/organization_detail?id=" + encodeURIComponent(org.name);
			viewLink.className = "fh-btn fh-btn-secondary";
			viewLink.textContent = "View";
			actionsTd.appendChild(viewLink);
			tr.appendChild(actionsTd);

			tbody.appendChild(tr);
		});

		table.style.display = "table";
	});
});
