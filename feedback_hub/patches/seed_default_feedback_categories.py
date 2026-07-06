import frappe

DEFAULT_CATEGORIES = ["Bug", "Feature Request", "Improvement", "Question", "Other"]


def execute():
	for category_name in DEFAULT_CATEGORIES:
		if frappe.db.exists("Feedback Category", category_name):
			continue
		frappe.get_doc({"doctype": "Feedback Category", "category_name": category_name}).insert(
			ignore_permissions=True
		)
