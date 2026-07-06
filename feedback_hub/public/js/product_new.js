document.getElementById("fh-product-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var productName = document.getElementById("product_name").value.trim();
	var description = document.getElementById("description").value.trim();

	submitBtn.disabled = true;
	submitBtn.textContent = "Creating...";

	fhApiCall("feedback_hub.product.api.create_product", {
		product_name: productName,
		description: description,
	}).then(function (res) {
		if (res.success) {
			window.location.href = "/product_detail?id=" + encodeURIComponent(res.data.name);
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Create Product";
		}
	});
});
