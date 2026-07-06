app_name = "feedback_hub"
app_title = "Feedback Hub"
app_publisher = "Feedback Hub"
app_description = "Collect and manage user feedback"
app_email = "admin@feedback-hub.localhost"
app_license = "mit"

# Fixtures
# --------
# Feedback Admin / Moderator / Viewer roles ship as data in fixtures/role.json
# and are (re)synced on every `bench migrate`, so they exist deterministically
# on any environment without manual setup (design.md Decision 6).
fixtures = [{"doctype": "Role", "filters": [["name", "in", ["Feedback Admin", "Moderator", "Viewer"]]]}]

# Intended permission policy (spec: role-permissions) - not yet enforced via
# concrete Custom DocPerm rows, since no Feedback doctype exists yet (that
# lands in a later module; see design.md Non-Goals):
#   Feedback Admin - full access (create, read, write, delete, approve)
#   Moderator      - read, write, approve (no delete)
#   Viewer         - read-only (default role assigned on signup)

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "feedback_hub",
# 		"logo": "/assets/feedback_hub/logo.png",
# 		"title": "Feedback Hub",
# 		"route": "/feedback_hub",
# 		"has_permission": "feedback_hub.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/feedback_hub/css/feedback_hub.css"
# app_include_js = "/assets/feedback_hub/js/feedback_hub.js"

# include js, css files in header of web template
# web_include_css = "/assets/feedback_hub/css/feedback_hub.css"
# web_include_js = "/assets/feedback_hub/js/feedback_hub.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "feedback_hub/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "feedback_hub/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings): Guests visiting
# "/" land on our own styled login page, never the Frappe Desk.
home_page = "login"

# website user home page (by Role): every feedback_hub role lands on our
# own dashboard, not /app (Desk) - see www/dashboard.py for page protection.
role_home_page = {
	"Feedback Admin": "dashboard",
	"Moderator": "dashboard",
	"Viewer": "dashboard",
}

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "feedback_hub.utils.jinja_methods",
# 	"filters": "feedback_hub.utils.jinja_filters"
# }

# Installation
# ------------

# after_install = "feedback_hub.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "feedback_hub.uninstall.before_uninstall"
# after_uninstall = "feedback_hub.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "feedback_hub.utils.before_app_install"
# after_app_install = "feedback_hub.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "feedback_hub.utils.before_app_uninstall"
# after_app_uninstall = "feedback_hub.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "feedback_hub.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# Organization/Organization Member (spec: organization-permissions),
# Product/Board (spec: product-board-permissions), and Feedback/Feedback
# Vote/Feedback Comment (spec: feedback-lifecycle etc). Base create/read/
# write/delete is granted to role "All" in each doctype's JSON (controller
# has_permission hooks can only deny, never grant beyond that); these hooks
# narrow it down to real organization membership/role checks, with Product/
# Board additionally scoped to the caller's currently active Organization,
# and Feedback/Vote/Comment delegating to the Board's own hook rather than
# re-deriving it (feedback_hub/organization/permissions.py,
# feedback_hub/product/permissions.py, feedback_hub/feedback/permissions.py).
permission_query_conditions = {
	"Organization": "feedback_hub.organization.permissions.get_permission_query_conditions_organization",
	"Organization Member": "feedback_hub.organization.permissions.get_permission_query_conditions_organization_member",
	"Product": "feedback_hub.product.permissions.get_permission_query_conditions_product",
	"Board": "feedback_hub.product.permissions.get_permission_query_conditions_board",
	"Feedback": "feedback_hub.feedback.permissions.get_permission_query_conditions_feedback",
	"Feedback Vote": "feedback_hub.feedback.permissions.get_permission_query_conditions_feedback_vote",
	"Feedback Comment": "feedback_hub.feedback.permissions.get_permission_query_conditions_feedback_comment",
	"Feedback Follower": "feedback_hub.feedback.permissions.get_permission_query_conditions_feedback_follower",
}

has_permission = {
	"Organization": "feedback_hub.organization.permissions.has_permission_organization",
	"Organization Member": "feedback_hub.organization.permissions.has_permission_organization_member",
	"Product": "feedback_hub.product.permissions.has_permission_product",
	"Board": "feedback_hub.product.permissions.has_permission_board",
	"Feedback": "feedback_hub.feedback.permissions.has_permission_feedback",
	"Feedback Vote": "feedback_hub.feedback.permissions.has_permission_feedback_vote",
	"Feedback Comment": "feedback_hub.feedback.permissions.has_permission_feedback_comment",
	"Feedback Category": "feedback_hub.feedback.categories.has_permission_feedback_category",
	"Anonymous Alias": "feedback_hub.feedback.anonymity.has_permission_anonymous_alias",
	"Feedback Follower": "feedback_hub.feedback.permissions.has_permission_feedback_follower",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"feedback_hub.tasks.all"
# 	],
# 	"daily": [
# 		"feedback_hub.tasks.daily"
# 	],
# 	"hourly": [
# 		"feedback_hub.tasks.hourly"
# 	],
# 	"weekly": [
# 		"feedback_hub.tasks.weekly"
# 	],
# 	"monthly": [
# 		"feedback_hub.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "feedback_hub.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "feedback_hub.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "feedback_hub.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["feedback_hub.utils.before_request"]
# after_request = ["feedback_hub.utils.after_request"]

# Job Events
# ----------
# before_job = ["feedback_hub.utils.before_job"]
# after_job = ["feedback_hub.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"feedback_hub.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

