// Feedback Hub - tiny fetch wrapper for calling feedback_hub whitelisted
// methods and rendering the standard {success, message, data} envelope.
function fhApiCall(method, args, httpMethod) {
	httpMethod = httpMethod || "POST";
	var url = "/api/method/" + method;
	var options = {
		method: httpMethod,
		headers: { "Content-Type": "application/json" },
		credentials: "same-origin",
	};
	if (window.csrf_token) {
		options.headers["X-Frappe-CSRF-Token"] = window.csrf_token;
	}

	if (httpMethod === "GET") {
		var params = new URLSearchParams(args || {}).toString();
		if (params) url += "?" + params;
	} else {
		options.body = JSON.stringify(args || {});
	}

	return fetch(url, options)
		.then(function (res) {
			return res.json().then(function (body) {
				// Frappe wraps whitelisted-method return values under "message".
				return body.message || { success: false, message: "Unexpected server response.", data: {} };
			});
		})
		.catch(function () {
			return { success: false, message: "Network error. Please try again.", data: {} };
		});
}

// Shared multipart file upload helper (profile photo, organization logo, ...).
function fhUploadFile(method, file, extraFields) {
	var formData = new FormData();
	formData.append("file", file);
	Object.keys(extraFields || {}).forEach(function (key) {
		formData.append(key, extraFields[key]);
	});

	var headers = {};
	if (window.csrf_token) headers["X-Frappe-CSRF-Token"] = window.csrf_token;

	return fetch("/api/method/" + method, {
		method: "POST",
		headers: headers,
		credentials: "same-origin",
		body: formData,
	})
		.then(function (res) {
			return res.json();
		})
		.then(function (body) {
			return body.message || { success: false, message: "Unexpected server response.", data: {} };
		})
		.catch(function () {
			return { success: false, message: "Network error uploading file.", data: {} };
		});
}

// Feedback Category is read via the generic, framework-provided
// frappe.client.get_list (DocPerm already grants read to role "All") rather
// than a bespoke feedback_hub endpoint - it returns a raw list under
// "message", not this app's {success, message, data} envelope, so it can't
// go through fhApiCall unchanged.
function fhFetchCategories() {
	var params = new URLSearchParams({
		doctype: "Feedback Category",
		fields: JSON.stringify(["name", "category_name"]),
		order_by: "category_name asc",
		limit_page_length: "0",
	});
	var headers = {};
	if (window.csrf_token) headers["X-Frappe-CSRF-Token"] = window.csrf_token;

	return fetch("/api/method/frappe.client.get_list?" + params.toString(), {
		method: "GET",
		headers: headers,
		credentials: "same-origin",
	})
		.then(function (res) {
			return res.json();
		})
		.then(function (body) {
			return body.message || [];
		})
		.catch(function () {
			return [];
		});
}

function fhShowAlert(el, message, variant) {
	el.textContent = message;
	el.className = "fh-alert fh-visible fh-alert-" + (variant || "error");
}

function fhHideAlert(el) {
	el.className = "fh-alert";
	el.textContent = "";
}
