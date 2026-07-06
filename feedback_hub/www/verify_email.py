import frappe

from feedback_hub.verification import check_verification_link

no_cache = 1


def get_context(context):
	email = frappe.form_dict.get("email")
	expires = frappe.form_dict.get("expires")
	signature = frappe.form_dict.get("_signature")

	result = check_verification_link(email, expires, signature)

	messages = {
		"verified": ("Email verified", "Your email has been verified. You can now log in.", "success"),
		"already_verified": ("Already verified", "Email already verified.", "info"),
		"expired": (
			"Link expired",
			"This verification link has expired. Please request a new one from the login page.",
			"error",
		),
		"invalid": ("Invalid link", "This verification link is invalid.", "error"),
	}
	title, message, variant = messages[result]

	context.no_header = True
	context.title = title
	context.message = message
	context.variant = variant
