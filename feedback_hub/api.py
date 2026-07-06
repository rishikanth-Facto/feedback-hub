import frappe
from frappe import _
from frappe.utils import validate_email_address
from frappe.utils.password import check_password

from feedback_hub.utils import api_response, display_roles, require_login, validate_password_strength
from feedback_hub.verification import check_verification_link, get_verification_url

DEFAULT_SIGNUP_ROLE = "Viewer"

# Profile photo constraints (Task 8.4 / spec "Profile Photo Validation").
ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
MAX_PHOTO_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB


# ---------------------------------------------------------------------------
# Signup (spec: user-registration)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def signup(first_name=None, last_name=None, email=None, password=None, confirm_password=None):
	missing = [
		label
		for label, value in (
			("First Name", first_name),
			("Last Name", last_name),
			("Email", email),
			("Password", password),
			("Confirm Password", confirm_password),
		)
		if not value
	]
	if missing:
		return api_response(False, _("Missing required field(s): {0}").format(", ".join(missing)))

	try:
		validate_email_address(email, throw=True)
	except frappe.InvalidEmailAddressError:
		return api_response(False, _("Please enter a valid email address."))

	if frappe.db.exists("User", email):
		return api_response(False, _("An account with this email already exists."))

	password_error = validate_password_strength(password)
	if password_error:
		return api_response(False, password_error)

	if password != confirm_password:
		return api_response(False, _("Password and Confirm Password do not match."))

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"last_name": last_name,
			"user_type": "Website User",
			"enabled": 0,
			"send_welcome_email": 0,
			"new_password": password,
		}
	)
	user.flags.ignore_permissions = True
	# Decision 9 (design.md): our own validate_password_strength() above is
	# authoritative for this flow. Frappe's separate zxcvbn-based password
	# policy (System Settings.enable_password_policy) would otherwise apply
	# its own, different rules on top and could reject a password that
	# already passed our explicit checks - skip it here to avoid that
	# confusing double-validation.
	user.flags.ignore_password_policy = True
	try:
		user.insert()
	except frappe.ValidationError as e:
		frappe.clear_messages()
		return api_response(False, str(e))
	user.add_roles(DEFAULT_SIGNUP_ROLE)

	# Decision 10 (design.md): send the verification email synchronously,
	# inside this same request, so a delivery failure rolls back the User
	# creation instead of stranding a permanently-disabled orphan account.
	try:
		_send_verification_email(email, first_name)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Feedback Hub: signup verification email failed")
		return api_response(
			False,
			_("We couldn't send your verification email. Please try signing up again in a moment."),
		)

	return api_response(True, _("Account created. Please check your email to verify your account."))


def _send_verification_email(email, first_name):
	url = get_verification_url(email)
	frappe.sendmail(
		recipients=[email],
		subject=_("Verify your Feedback Hub account"),
		message=_(
			"Hi {0},<br><br>"
			"Thanks for signing up for Feedback Hub. Please verify your email address "
			"by clicking the link below:<br><br>"
			'<a href="{1}">{1}</a><br><br>'
			"This link expires in 24 hours."
		).format(first_name, url),
		now=True,
	)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def resend_verification_email(email=None):
	"""Guards against Decision 10's queued-delivery risk: lets a user whose
	verification email never arrived request a fresh link, rather than being
	permanently stuck with a disabled, unverifiable account."""
	if not email:
		return api_response(False, _("Email is required."))

	# Same non-revealing response regardless of whether the account exists,
	# mirroring the forgot-password pattern (spec: password-reset).
	generic_message = _("If an unverified account exists for this email, a new verification link has been sent.")

	user = frappe.db.get_value("User", email, ["enabled", "first_name"], as_dict=True)
	if not user or user.enabled:
		return api_response(True, generic_message)

	try:
		_send_verification_email(email, user.first_name)
	except Exception:
		frappe.log_error(title="Feedback Hub: resend verification email failed")

	return api_response(True, generic_message)


# ---------------------------------------------------------------------------
# Email verification (spec: email-verification)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["GET"])
def verify_email(email=None, expires=None, _signature=None):
	result = check_verification_link(email, expires, _signature)
	messages = {
		"verified": _("Your email has been verified. You can now log in."),
		"already_verified": _("Email already verified."),
		"expired": _("This verification link has expired. Please request a new one."),
		"invalid": _("This verification link is invalid."),
	}
	return api_response(result in ("verified", "already_verified"), messages[result], {"result": result})


# ---------------------------------------------------------------------------
# Login (spec: authentication)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(usr=None, pwd=None):
	if not usr or not pwd:
		return api_response(False, _("Email and password are required."))

	# Check credentials ourselves first (rather than delegating straight to
	# LoginManager.authenticate) so we can return a distinct "email not
	# verified" message for correct-password-but-unverified accounts,
	# without revealing that distinction for wrong-password attempts.
	try:
		checked_user = check_password(usr, pwd)
	except frappe.AuthenticationError:
		return api_response(False, _("Invalid email or password."))

	if checked_user != "Administrator" and not frappe.db.get_value("User", checked_user, "enabled"):
		return api_response(False, _("Please verify your email before logging in."))

	frappe.local.login_manager.authenticate(user=checked_user, pwd=pwd)
	frappe.local.login_manager.post_login()

	return api_response(
		True, _("Login successful"), {"user": checked_user, "roles": display_roles(checked_user)}
	)


# ---------------------------------------------------------------------------
# Forgot / reset password (spec: password-reset)
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
def forgot_password(email=None):
	if not email:
		return api_response(False, _("Email is required."))

	# Delegate to Frappe's own reset_password (frappe.core.doctype.user.user):
	# it already returns the same generic message whether or not the email
	# exists, is rate-limited, and generates the /update-password reset link.
	from frappe.core.doctype.user.user import reset_password as core_reset_password

	frappe.clear_messages()
	core_reset_password(user=email)
	return api_response(True, _("If this email is registered with us, we have sent password reset instructions."))


# ---------------------------------------------------------------------------
# Profile (spec: user-profile)
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def profile(**kwargs):
	# Task 8.6 / spec "Profile Endpoint Always Scoped To The Caller": any
	# client-supplied user/email is accepted (via **kwargs) and ignored -
	# the profile is always the current session's own user.
	require_login()
	user = frappe.session.user
	doc = frappe.get_cached_doc("User", user)
	data = {
		"first_name": doc.first_name,
		"last_name": doc.last_name,
		"email": doc.email,
		"roles": display_roles(user),
		"last_login": doc.last_login,
		"creation": doc.creation,
		"user_image": doc.user_image,
	}
	return api_response(True, _("Profile fetched"), data)


@frappe.whitelist(methods=["POST", "PUT"])
def update_profile(first_name=None, last_name=None, **kwargs):
	# Task 8.6: any client-supplied user/email in kwargs is ignored - always
	# resolve to frappe.session.user, never a caller-supplied target.
	require_login()
	user = frappe.get_doc("User", frappe.session.user)

	if first_name:
		user.first_name = first_name
	if last_name:
		user.last_name = last_name

	user.flags.ignore_permissions = True
	user.save()

	return api_response(True, _("Profile updated."))


@frappe.whitelist(methods=["POST"])
def update_profile_photo():
	require_login()

	uploaded = frappe.request.files.get("file") if frappe.request else None
	if not uploaded:
		return api_response(False, _("No file uploaded."))

	filename = uploaded.filename or ""
	extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
	if extension not in ALLOWED_PHOTO_EXTENSIONS:
		return api_response(
			False, _("Unsupported file type. Allowed types: {0}").format(", ".join(sorted(ALLOWED_PHOTO_EXTENSIONS)))
		)

	content = uploaded.read()
	if len(content) > MAX_PHOTO_SIZE_BYTES:
		return api_response(False, _("File is too large. Maximum size is 2 MB."))

	user_name = frappe.session.user

	# Decision 11 (design.md): store via the File doctype, then point
	# User.user_image at the resulting file URL - the same mechanism
	# Frappe's own avatar upload widget uses.
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": "User",
			"attached_to_name": user_name,
			"attached_to_field": "user_image",
			"is_private": 0,
		}
	)
	file_doc.flags.ignore_permissions = True
	try:
		file_doc.save()
		frappe.db.set_value("User", user_name, "user_image", file_doc.file_url)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Feedback Hub: profile photo upload failed")
		return api_response(False, _("We couldn't save your profile photo. Please try again."))

	return api_response(True, _("Profile photo updated."), {"user_image": file_doc.file_url})
