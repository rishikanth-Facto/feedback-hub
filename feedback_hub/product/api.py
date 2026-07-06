import frappe
from frappe import _

from feedback_hub.organization.api import handle_errors
from feedback_hub.product import service
from feedback_hub.utils import api_response, require_login

# Reuses feedback_hub.organization.api.handle_errors as-is (design.md
# Decision 2) - it only inspects generic Frappe exception classes, so it is
# not organization-specific and importing it here is a legitimate reuse
# rather than a layering violation.

# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def create_product(product_name=None, description=None):
	require_login()
	data = service.create_product(product_name, description=description)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Product created."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_products():
	require_login()
	data = service.list_products()
	return api_response(True, _("Products fetched."), {"products": data})


@frappe.whitelist(methods=["GET"])
@handle_errors
def get_product(product=None):
	require_login()
	data = service.get_product(product)
	return api_response(True, _("Product fetched."), data)


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_product(product=None, product_name=None, description=None, status=None):
	require_login()
	data = service.update_product(product, product_name=product_name, description=description, status=status)
	return api_response(True, _("Product updated."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def delete_product(product=None, force=False):
	require_login()
	data = service.delete_product(product, force=frappe.utils.cint(force))
	return api_response(True, _("Product deleted."), data)


# ---------------------------------------------------------------------------
# Board CRUD
# ---------------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@handle_errors
def create_board(product=None, board_name=None, visibility=None, description=None):
	require_login()
	data = service.create_board(product, board_name, visibility, description=description)
	frappe.local.response["http_status_code"] = 201
	return api_response(True, _("Board created."), data)


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_boards(product=None):
	require_login()
	data = service.list_boards(product)
	return api_response(True, _("Boards fetched."), {"boards": data})


@frappe.whitelist(methods=["GET"])
@handle_errors
def list_visible_products():
	require_login()
	data = service.list_visible_products()
	return api_response(True, _("Products fetched."), {"products": data})


@frappe.whitelist(methods=["GET"])
@handle_errors
def get_board(board=None):
	require_login()
	data = service.get_board(board)
	return api_response(True, _("Board fetched."), data)


@frappe.whitelist(methods=["POST", "PUT"])
@handle_errors
def update_board(board=None, board_name=None, visibility=None, description=None):
	require_login()
	data = service.update_board(board, board_name=board_name, visibility=visibility, description=description)
	return api_response(True, _("Board updated."), data)


@frappe.whitelist(methods=["POST", "DELETE"])
@handle_errors
def delete_board(board=None):
	require_login()
	data = service.delete_board(board)
	return api_response(True, _("Board deleted."), data)
