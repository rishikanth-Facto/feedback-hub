import frappe


def emit_event(event_type, feedback_doc, actor=None, **extra):
	"""Trigger-only notification event (Module 5 design.md Decision 11) - no
	subscriber resolution or delivery here, only a payload on Frappe's
	existing realtime bus for a future Notifications module to consume."""
	frappe.publish_realtime(
		"feedback_hub:engagement",
		{
			"event": event_type,
			"feedback": feedback_doc.name,
			"organization": feedback_doc.organization,
			"actor": actor or frappe.session.user,
			**extra,
		},
	)
