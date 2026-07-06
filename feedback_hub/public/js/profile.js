document.getElementById("fh-profile-form").addEventListener("submit", function (e) {
	e.preventDefault();
	var alertEl = document.getElementById("fh-alert");
	var submitBtn = document.getElementById("fh-submit");
	fhHideAlert(alertEl);

	submitBtn.disabled = true;
	submitBtn.textContent = "Saving...";

	var firstName = document.getElementById("first_name").value.trim();
	var lastName = document.getElementById("last_name").value.trim();
	var photoFile = document.getElementById("photo").files[0];

	var tasks = [fhApiCall("feedback_hub.api.update_profile", { first_name: firstName, last_name: lastName })];
	if (photoFile) {
		tasks.push(fhUploadFile("feedback_hub.api.update_profile_photo", photoFile));
	}

	Promise.all(tasks).then(function (results) {
		var failed = results.find(function (r) {
			return !r.success;
		});
		if (failed) {
			fhShowAlert(alertEl, failed.message, "error");
		} else {
			fhShowAlert(alertEl, "Profile updated.", "success");
			var photoResult = results[1];
			if (photoResult && photoResult.data && photoResult.data.user_image) {
				var avatar = document.getElementById("fh-avatar-preview");
				avatar.src = photoResult.data.user_image;
				avatar.style.display = "";
			}
		}
		submitBtn.disabled = false;
		submitBtn.textContent = "Save Changes";
	});
});
