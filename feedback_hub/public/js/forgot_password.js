document.getElementById("fh-forgot-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var email = document.getElementById("email").value.trim();

	submitBtn.disabled = true;
	submitBtn.textContent = "Sending...";

	fhApiCall("feedback_hub.api.forgot_password", { email: email }).then(function (res) {
		// Always show the same generic message regardless of success/failure
		// shape, to avoid revealing whether the email exists.
		fhShowAlert(alertEl, res.message, res.success ? "success" : "info");
		submitBtn.disabled = false;
		submitBtn.textContent = "Send Reset Link";
	});
});
