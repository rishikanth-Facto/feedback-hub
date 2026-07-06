document.addEventListener("DOMContentLoaded", function () {
	var titleEl = document.getElementById("fh-accept-title");
	var alertEl = document.getElementById("fh-accept-alert");
	var actionsEl = document.getElementById("fh-accept-actions");

	function showActions(links) {
		actionsEl.innerHTML = "";
		links.forEach(function (link) {
			var a = document.createElement("a");
			a.className = "fh-btn " + (link.primary ? "fh-btn-primary" : "fh-btn-secondary");
			a.href = link.href;
			a.textContent = link.label;
			actionsEl.appendChild(a);
		});
		actionsEl.style.display = "flex";
	}

	if (!window.fhInvitationToken) {
		titleEl.textContent = "Invalid Invitation Link";
		fhShowAlert(alertEl, "This invitation link is missing its token.", "error");
		showActions([{ href: "/login", label: "Go to Log In", primary: true }]);
		return;
	}

	fhApiCall("feedback_hub.organization.api.accept_invitation", { token: window.fhInvitationToken }).then(
		function (res) {
			var result = (res.data && res.data.result) || "invalid";

			if (result === "accepted") {
				titleEl.textContent = "You're In!";
				fhShowAlert(alertEl, res.message, "success");
				showActions([{ href: "/organizations", label: "Go to Organizations", primary: true }]);
			} else if (result === "login_required") {
				titleEl.textContent = "Log In To Continue";
				fhShowAlert(alertEl, res.message + " After logging in, click this same invitation link again.", "info");
				showActions([{ href: "/login", label: "Log In", primary: true }]);
			} else if (result === "signup_required") {
				titleEl.textContent = "Sign Up To Continue";
				fhShowAlert(
					alertEl,
					res.message + " After verifying your email and logging in, click this same invitation link again.",
					"info"
				);
				showActions([{ href: "/signup", label: "Sign Up", primary: true }]);
			} else {
				titleEl.textContent = "Invitation Not Accepted";
				fhShowAlert(alertEl, res.message, "error");
				showActions([{ href: "/dashboard", label: "Go to Dashboard", primary: true }]);
			}
		}
	);
});
