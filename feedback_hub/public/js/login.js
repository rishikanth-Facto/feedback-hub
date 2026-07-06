document.getElementById("fh-login-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var usr = document.getElementById("usr").value.trim();
	var pwd = document.getElementById("pwd").value;

	submitBtn.disabled = true;
	submitBtn.textContent = "Logging in...";

	fhApiCall("feedback_hub.api.login", { usr: usr, pwd: pwd }).then(function (res) {
		if (res.success) {
			window.location.href = "/dashboard";
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Log In";
		}
	});
});
