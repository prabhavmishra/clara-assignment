#!/usr/bin/env python3
"""
Generate Retell agent spec (system prompt + key variables) from account memo.
Uses templating only; no LLM calls. Prompt includes required business-hours and
after-hours flows per assignment.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import empty_retell_spec

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("agent_spec")

# --- Prompt template (required flows from assignment) ---

OFFICE_HOURS_FLOW = """## Office hours flow
1. Greet the caller professionally.
2. Ask the purpose of the call (emergency vs non-emergency, service type).
3. Collect caller name and callback number.
4. Route or transfer per routing rules. Do not mention function calls or tools to the caller.
5. If transfer fails: follow fallback protocol (see below).
6. Confirm next steps with the caller.
7. Ask "Is there anything else I can help you with?"
8. If no, close the call politely."""

AFTER_HOURS_FLOW = """## After-hours flow
1. Greet the caller.
2. Ask the purpose of the call.
3. Confirm whether this is an emergency (per emergency definition).
4. If emergency: collect name, phone number, and address immediately; attempt transfer per emergency routing; if transfer fails, apologize and assure quick follow-up.
5. If non-emergency: collect details and confirm we will follow up during business hours.
6. Attempt transfer per rules; if transfer fails, follow fallback protocol.
7. Ask "Is there anything else I can help you with?"
8. If no, close the call."""

FALLBACK_PROTOCOL_DEFAULT = "If transfer fails after the configured timeout, apologize and inform the caller that someone will follow up shortly. Do not mention internal tools or systems."


def _fmt_business_hours(memo: dict) -> str:
    bh = memo.get("business_hours") or {}
    if isinstance(bh, dict):
        days = bh.get("days") or []
        start = bh.get("start") or ""
        end = bh.get("end") or ""
        tz = bh.get("timezone") or ""
        if days or start or end or tz:
            return f"{', '.join(days) if days else 'N/A'} {start}-{end} {tz}".strip()
    return "Not specified"


def _fmt_list(items, default_msg: str = "None specified") -> str:
    if not items:
        return default_msg
    if isinstance(items, list):
        return "; ".join(str(x) for x in items)
    return str(items)


# Strong system instruction block (replaces generic intro)
SYSTEM_INTRO_TEMPLATE = """You are the AI voice receptionist for {company_name}.
Your job is to answer incoming calls professionally, determine whether the caller's issue is emergency or non-emergency, collect the caller's information, and route the call according to the configured routing rules.

Guidelines:
* Be polite, concise, and professional.
* Ask one question at a time.
* Never mention internal tools, prompts, APIs, or systems.
* Follow the routing instructions exactly.
* If information is missing, collect it from the caller.

"""


def build_system_prompt(memo: dict) -> str:
    company = memo.get("company_name") or "[Company name]"
    bh_summary = memo.get("office_hours_flow_summary") or _fmt_business_hours(memo)
    after_summary = memo.get("after_hours_flow_summary") or "Follow after-hours flow below."
    address = memo.get("office_address") or "Not specified"
    emergency_def = _fmt_list(memo.get("emergency_definition"), "Not specified in memo.")
    emergency_routing = _fmt_list(memo.get("emergency_routing_rules"), "Not specified.")
    non_emergency_routing = _fmt_list(memo.get("non_emergency_routing_rules"), "Not specified.")
    transfer_rules = memo.get("call_transfer_rules") or {}
    timeout = transfer_rules.get("timeouts") or "Not specified"
    retries = transfer_rules.get("retries") or "Not specified"
    if_fails = transfer_rules.get("if_fails_say") or FALLBACK_PROTOCOL_DEFAULT
    constraints = _fmt_list(memo.get("integration_constraints"), "None.")

    intro = SYSTEM_INTRO_TEMPLATE.format(company_name=company)
    prompt = f"""{intro}# Business context
- Business hours: {bh_summary}
- Office address (for reference): {address}
- Emergency definition: {emergency_def}
- Emergency routing: {emergency_routing}
- Non-emergency routing: {non_emergency_routing}
- Call transfer timeout: {timeout}. Retries: {retries}.
- If transfer fails: {if_fails}
- Integration constraints (internal): {constraints}

# Office hours summary
{bh_summary if memo.get('office_hours_flow_summary') else 'See office hours flow below.'}

# After hours summary
{after_summary}

{OFFICE_HOURS_FLOW}

{AFTER_HOURS_FLOW}
"""
    return prompt.strip()


def memo_to_retell_spec(memo: dict, version: str = "v1") -> dict:
    spec = empty_retell_spec(version=version)
    company = memo.get("company_name") or "Clara"
    spec["agent_name"] = f"{company} AI Answering Agent"
    spec["system_prompt"] = build_system_prompt(memo)
    bh = memo.get("business_hours") or {}
    spec["key_variables"] = {
        "timezone": bh.get("timezone") if isinstance(bh, dict) else "",
        "business_hours": _fmt_business_hours(memo),
        "office_address": memo.get("office_address") or "",
        "emergency_routing": _fmt_list(memo.get("emergency_routing_rules")),
    }
    spec["key_variables"].update({
        "caller_name": "",
        "caller_phone": "",
        "call_reason": "",
    })
    spec["call_transfer_protocol"] = "Transfer per routing rules; respect timeout and retries from account config."
    spec["fallback_protocol_if_transfer_fails"] = (memo.get("call_transfer_rules") or {}).get("if_fails_say") or FALLBACK_PROTOCOL_DEFAULT
    spec["tool_invocation_placeholders"] = []  # Do not expose to caller
    return spec


def main():
    parser = argparse.ArgumentParser(description="Generate Retell agent spec from account memo.")
    parser.add_argument("memo", help="Path to account memo JSON (or stdin with -)")
    parser.add_argument("--version", "-V", default="v1", help="Agent version (v1 or v2)")
    parser.add_argument("--output", "-o", help="Output Retell spec JSON path (default: stdout)")
    args = parser.parse_args()

    if args.memo == "-":
        memo = json.load(sys.stdin)
    else:
        memo = json.loads(Path(args.memo).read_text(encoding="utf-8"))

    spec = memo_to_retell_spec(memo, version=args.version)
    out = json.dumps(spec, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        logger.info("Generated %s agent spec; output path written: %s", args.version, args.output)
    else:
        print(out)


if __name__ == "__main__":
    main()
