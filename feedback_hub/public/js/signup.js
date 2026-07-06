document.getElementById("fh-signup-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	var payload = {
		first_name: document.getElementById("first_name").value.trim(),
		last_name: document.getElementById("last_name").value.trim(),
		email: document.getElementById("email").value.trim(),
		password: document.getElementById("password").value,
		confirm_password: document.getElementById("confirm_password").value,
	};

	// Client-side UX validation only - mirrors, does not replace, the
	// authoritative server-side checks in feedback_hub.api.signup.
	if (payload.password !== payload.confirm_password) {
		fhShowAlert(alertEl, "Password and Confirm Password do not match.", "error");
		return;
	}

	submitBtn.disabled = true;
	submitBtn.textContent = "Creating account...";

	fhApiCall("feedback_hub.api.signup", payload).then(function (res) {
		if (res.success) {
			fhShowAlert(alertEl, res.message, "success");
			document.getElementById("fh-signup-form").reset();
			submitBtn.textContent = "Account created";
		} else {
			fhShowAlert(alertEl, res.message, "error");
			submitBtn.disabled = false;
			submitBtn.textContent = "Sign Up";
		}
	});
});
