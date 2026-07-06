document.addEventListener("DOMContentLoaded", function () {
	var loading = document.getElementById("fh-product-list-loading");
	var table = document.getElementById("fh-product-table");
	var tbody = document.getElementById("fh-product-table-body");
	var empty = document.getElementById("fh-product-empty");

	fhApiCall("feedback_hub.product.api.list_products", {}, "GET").then(function (res) {
		loading.style.display = "none";
		if (!res.success) {
			fhToast(res.message, "error");
			return;
		}

		var products = res.data.products || [];
		if (!products.length) {
			empty.style.display = "block";
			return;
		}

		products.forEach(function (product) {
			var tr = document.createElement("tr");

			var nameTd = document.createElement("td");
			var link = document.createElement("a");
			link.href = "/product_detail?id=" + encodeURIComponent(product.name);
			link.textContent = product.product_name;
			nameTd.appendChild(link);
			tr.appendChild(nameTd);

			var slugTd = document.createElement("td");
			slugTd.className = "fh-mono";
			slugTd.textContent = product.slug;
			tr.appendChild(slugTd);

			var statusTd = document.createElement("td");
			var badge = document.createElement("span");
			badge.className = fhStatusBadgeClass(product.status);
			badge.textContent = product.status;
			statusTd.appendChild(badge);
			tr.appendChild(statusTd);

			var ownerTd = document.createElement("td");
			ownerTd.textContent = product.product_owner || "-";
			tr.appendChild(ownerTd);

			var actionsTd = document.createElement("td");
			actionsTd.className = "fh-table-actions";
			var viewLink = document.createElement("a");
			viewLink.href = "/product_detail?id=" + encodeURIComponent(product.name);
			viewLink.className = "fh-btn fh-btn-secondary";
			viewLink.textContent = "View";
			actionsTd.appendChild(viewLink);
			tr.appendChild(actionsTd);

			tbody.appendChild(tr);
		});

		table.style.display = "table";
	});
});
