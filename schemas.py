"""
JSON schemas and default structures for account memo and Retell agent spec.
Used across extraction, apply_updates, and prompt generation.
"""

from typing import Any

# --- Account Memo ---

ACCOUNT_MEMO_FIELDS = [
    "account_id",
    "company_name",
    "business_hours",
    "office_address",
    "services_supported",
    "emergency_definition",
    "emergency_routing_rules",
    "non_emergency_routing_rules",
    "call_transfer_rules",
    "integration_constraints",
    "after_hours_flow_summary",
    "office_hours_flow_summary",
    "questions_or_unknowns",
    "notes",
]


def empty_account_memo(account_id: str = "") -> dict[str, Any]:
    return {
        "account_id": account_id,
        "company_name": "",
        "business_hours": {"days": [], "start": "", "end": "", "timezone": ""},
        "office_address": "",
        "services_supported": [],
        "emergency_definition": [],
        "emergency_routing_rules": [],
        "non_emergency_routing_rules": [],
        "call_transfer_rules": {"timeouts": "", "retries": "", "if_fails_say": ""},
        "integration_constraints": [],
        "after_hours_flow_summary": "",
        "office_hours_flow_summary": "",
        "questions_or_unknowns": [],
        "notes": "",
    }


# --- Retell Agent Spec ---

def empty_retell_spec(version: str = "v1") -> dict[str, Any]:
    return {
        "version": version,
        "agent_name": "",
        "voice_style": "professional",
        "system_prompt": "",
        "key_variables": {
            "timezone": "",
            "business_hours": "",
            "office_address": "",
            "emergency_routing": "",
        },
        "tool_invocation_placeholders": [],
        "call_transfer_protocol": "",
        "fallback_protocol_if_transfer_fails": "",
    }


RETELL_SPEC_FIELDS = [
    "version",
    "agent_name",
    "voice_style",
    "system_prompt",
    "key_variables",
    "tool_invocation_placeholders",
    "call_transfer_protocol",
    "fallback_protocol_if_transfer_fails",
]
