import frappe


def make_user(email, first_name="Test"):
	if frappe.db.exists("User", email):
		return frappe.get_doc("User", email)

	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": first_name,
			"user_type": "Website User",
			"enabled": 1,
			"send_welcome_email": 0,
			"new_password": "TestPass@123",
		}
	)
	user.flags.ignore_permissions = True
	user.flags.ignore_password_policy = True
	user.insert()
	return user
