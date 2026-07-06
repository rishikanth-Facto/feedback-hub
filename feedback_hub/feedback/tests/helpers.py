import frappe

from feedback_hub.product import service as product_service


def make_board(organization, board_name, visibility="Public"):
	"""Create a Product + Board under `organization` for feedback tests. The
	caller must already be an Active Organization Admin/Product Owner of
	`organization` with it as their active context (make_active_organization)."""
	product = product_service.create_product("Feedback Test Product " + frappe.generate_hash(length=6))
	return product_service.create_board(product["name"], board_name, visibility)
