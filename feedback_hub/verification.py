import hmac
import time

import frappe
from frappe.utils import get_url
from frappe.utils.verified_command import get_signed_params

# Frappe's verified_command.verify_request() auto-renders its own "Invalid Link"
# response page when the signature check fails (see frappe/utils/verified_command.py),
# which is designed for the whitelisted-API dispatch path, not for a custom-styled
# www page. So verification here reuses only the public get_signed_params() helper
# to compute/compare the signature ourselves, giving full control over which of our
# own (verified / already-verified / expired / invalid) states gets rendered.
VERIFICATION_LINK_VALIDITY_SECONDS = 24 * 60 * 60  # 24 hours


def get_verification_url(email):
	expires = int(time.time()) + VERIFICATION_LINK_VALIDITY_SECONDS
	signed = get_signed_params({"email": email, "expires": expires})
	return get_url(f"/verify_email?{signed}")


def _expected_signature(email, expires):
	signed = get_signed_params({"email": email, "expires": expires})
	return signed.rsplit("_signature=", 1)[-1]


def check_verification_link(email, expires, signature):
	"""Returns one of: "verified", "already_verified", "expired", "invalid"."""
	if not (email and expires and signature):
		return "invalid"

	try:
		expires = int(expires)
	except (TypeError, ValueError):
		return "invalid"

	expected = _expected_signature(email, expires)
	if not hmac.compare_digest(expected, signature):
		return "invalid"

	if time.time() > expires:
		return "expired"

	if not frappe.db.exists("User", email):
		return "invalid"

	if frappe.db.get_value("User", email, "enabled"):
		return "already_verified"

	frappe.db.set_value("User", email, "enabled", 1)
	frappe.db.commit()
	return "verified"
