#!/usr/bin/env python3
"""
Extract structured account memo from demo call transcript using rule-based patterns.
Never invents data; missing info goes into questions_or_unknowns.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

# Allow importing from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import empty_account_memo, ACCOUNT_MEMO_FIELDS

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("extract_demo")

# --- Regex / heuristic patterns (rule-based only) ---

COMPANY_PATTERNS = [
    re.compile(r"(?:we're|we are)\s+([A-Za-z0-9][^.?,\n]{2,80}?)(?:\s*\.|,|\?|\s+We|\s+Our|$)", re.I),
    re.compile(r"(?:company|business)\s+(?:name\s+is\s+)?(?:called\s+)?([A-Za-z0-9][^.?,\n]{2,80}?)(?:\s*\.|,|\?|$)", re.I),
    re.compile(r"^(?:company\s+name:?\s*)([A-Za-z0-9][A-Za-z0-9\s&\.\-]{2,60}?)\s*$", re.M | re.I),
]

BUSINESS_HOURS_DAYS = re.compile(
    r"(?:mon(?:day)?|tue(?:s)?|wed(?:nesday)?|thu(?:rs)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    r"(?:\s*[-–to]+\s*(?:mon|tue|wed|thu|fri|sat|sun))?",
    re.I,
)
BUSINESS_HOURS_TIME = re.compile(
    r"(?:hours?|open)\s*(?:are|:)?\s*[\w\s]*(\d{1,2})\s*(?::\d{2})?\s*(am|pm)?\s*[-–to]+\s*(\d{1,2})\s*(?::\d{2})?\s*(am|pm)?",
    re.I,
)
# Fallback: "9 to 5" or "9am-5pm" without "hours" keyword
BUSINESS_HOURS_TIME_ALT = re.compile(
    r"(\d{1,2})\s*(am|pm)?\s*[-–to]+\s*(\d{1,2})\s*(am|pm)?",
    re.I,
)
TIMEZONE_PATTERN = re.compile(
    r"\b(EST|EDT|CST|CDT|MST|MDT|PST|PDT|Eastern|Central|Mountain|Pacific|UTC[-+]?\d*)\b",
    re.I,
)

ADDRESS_PATTERNS = [
    re.compile(r"(?:address|located at|office (?:is )?at)\s*[:\-]?\s*([0-9]+\s+[A-Za-z0-9\s,\.\-]+?(?:street|st|ave|avenue|blvd|road|rd|drive|dr)\.?[\s,Suite\d]*[A-Za-z0-9\s,\.\-]{0,40}?)(?:\s*\n|\.\s|$)", re.I),
    re.compile(r"(\d{1,6}\s+[\w\s]+?(?:street|st|ave|blvd|road|rd|drive|dr)\.?\s*(?:Suite\s*\d+[\w\s,\.\-]*)?)(?:\s*\n|\.|$)", re.I),
]

SERVICES_KEYWORDS = [
    "sprinkler", "fire alarm", "fire protection", "extinguisher", "HVAC",
    "electrical", "inspection", "emergency", "service", "maintenance", "alarm",
]

EMERGENCY_KEYWORDS = [
    "sprinkler leak", "fire", "alarm", "emergency", "urgent", "water leak",
    "flood", "break-in", "life safety",
]

ROUTING_PATTERNS = [
    re.compile(r"(?:transfer|route|send)\s+(?:calls?|to)\s+(?:the\s+)?([^\n\.]+?)(?:\.|,|$)", re.I),
    re.compile(r"(?:after\s+hours?|afterhours?)\s+(?:we\s+)?(?:transfer|route|send)\s+to\s+([^\n\.]+)", re.I),
    re.compile(r"(?:call|contact|notify)\s+([^\n\.]+?)\s+(?:for|on|when)", re.I),
]

INTEGRATION_PATTERNS = [
    re.compile(r"(?:never|don't|do not)\s+([^\n\.]+?ServiceTrade[^\n\.]*|create[^\n\.]*in\s+ServiceTrade)", re.I),
    re.compile(r"ServiceTrade\s*[:\-]?\s*([^\n\.]+)", re.I),
]

TRANSFER_TIMEOUT = re.compile(r"(?:timeout|after)\s+(?:transfer\s+)?(\d+)\s*(?:sec|second|min|minute)", re.I)
TRANSFER_RETRIES = re.compile(r"(?:retry|retries?)\s*(?:of\s*)?(\d+)", re.I)


def extract_company_name(text: str) -> str:
    for pat in COMPANY_PATTERNS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip()
            if len(name) > 2 and len(name) < 120 and "main stuff" not in name.lower():
                return name
    return ""


def extract_business_hours(text: str) -> dict:
    out = {"days": [], "start": "", "end": "", "timezone": ""}
    # Days: "Monday through Friday" style
    for m in BUSINESS_HOURS_DAYS.finditer(text):
        d = m.group(0).strip()
        if d and len(d) > 1 and d not in out["days"]:
            out["days"].append(d)
    # Time range
    m = BUSINESS_HOURS_TIME.search(text)
    if m:
        out["start"] = m.group(1) + (f" {m.group(2)}" if m.group(2) else "am")
        out["end"] = m.group(3) + (f" {m.group(4)}" if m.group(4) else "pm")
    else:
        m2 = BUSINESS_HOURS_TIME_ALT.search(text)
        if m2:
            out["start"] = m2.group(1) + (f" {m2.group(2)}" if m2.group(2) else "am")
            out["end"] = m2.group(3) + (f" {m2.group(4)}" if m2.group(4) else "pm")
    # Timezone
    tz = TIMEZONE_PATTERN.search(text)
    if tz:
        out["timezone"] = tz.group(1).strip()
    return out


def extract_address(text: str) -> str:
    for pat in ADDRESS_PATTERNS:
        m = pat.search(text)
        if m:
            addr = m.group(1).strip()
            # Trim at first newline or trailing dialogue
            addr = addr.split("\n")[0].strip()
            if "Rep:" in addr or "Client:" in addr:
                addr = addr.split("Rep:")[0].split("Client:")[0].strip()
            return addr[:200]
    return ""


def extract_services(text: str) -> list:
    found = []
    lower = text.lower()
    for s in SERVICES_KEYWORDS:
        if s.lower() in lower and s not in found:
            found.append(s)
    return found


def extract_emergency_definition(text: str) -> list:
    found = []
    lower = text.lower()
    for s in EMERGENCY_KEYWORDS:
        if s.lower() in lower and s not in found:
            found.append(s)
    return found


def extract_routing_rules(text: str) -> list:
    rules = []
    for pat in ROUTING_PATTERNS:
        for m in pat.finditer(text):
            r = m.group(1).strip()
            if r and len(r) < 200 and r not in rules:
                rules.append(r)
    return rules


def extract_integration_constraints(text: str) -> list:
    constraints = []
    for pat in INTEGRATION_PATTERNS:
        for m in pat.finditer(text):
            c = m.group(1).strip() if m.lastindex else m.group(0).strip()
            if c and c not in constraints:
                constraints.append(c[:200])
    return constraints


def extract_transfer_rules(text: str) -> dict:
    out = {"timeouts": "", "retries": "", "if_fails_say": ""}
    m = TRANSFER_TIMEOUT.search(text)
    if m:
        out["timeouts"] = m.group(1) + " seconds"
    m = TRANSFER_RETRIES.search(text)
    if m:
        out["retries"] = m.group(1)
    if "if transfer fails" in text.lower() or "when transfer fails" in text.lower():
        # Capture next sentence
        idx = text.lower().find("if transfer fails")
        if idx == -1:
            idx = text.lower().find("when transfer fails")
        snippet = text[idx : idx + 200]
        out["if_fails_say"] = snippet.strip()[:150]
    return out


def build_questions_or_unknowns(memo: dict) -> list:
    q = []
    if not memo.get("company_name"):
        q.append("Company name not stated in transcript.")
    if not memo.get("business_hours", {}).get("start"):
        q.append("Business hours start/end not clearly stated.")
    if not memo.get("business_hours", {}).get("timezone"):
        q.append("Timezone not stated.")
    if not memo.get("office_address"):
        q.append("Office address not provided.")
    if not memo.get("emergency_definition"):
        q.append("Emergency definition not clearly specified.")
    if not memo.get("emergency_routing_rules"):
        q.append("Emergency routing rules not specified.")
    if not memo.get("call_transfer_rules", {}).get("timeouts"):
        q.append("Call transfer timeout not specified.")
    return q


def extract_demo_data(transcript_path: str, account_id: str) -> dict:
    path = Path(transcript_path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    logger.info("Demo stage starting for account %s", account_id)
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.strip():
        logger.warning("Empty transcript: %s", transcript_path)
    logger.info("Demo transcript parsed: %s", transcript_path)

    memo = empty_account_memo(account_id)
    raw_company = extract_company_name(text)
    memo["company_name"] = raw_company.strip() if raw_company else ""
    memo["business_hours"] = extract_business_hours(text)
    memo["office_address"] = extract_address(text)
    memo["services_supported"] = extract_services(text)
    memo["emergency_definition"] = extract_emergency_definition(text)
    emergency_routing = extract_routing_rules(text)
    memo["emergency_routing_rules"] = emergency_routing
    memo["non_emergency_routing_rules"] = []  # Could add separate patterns if needed
    memo["call_transfer_rules"] = extract_transfer_rules(text)
    memo["integration_constraints"] = extract_integration_constraints(text)
    memo["after_hours_flow_summary"] = ""
    memo["office_hours_flow_summary"] = ""
    memo["questions_or_unknowns"] = build_questions_or_unknowns(memo)
    memo["notes"] = "Extracted from demo call transcript (rule-based)."

    unknowns = memo.get("questions_or_unknowns") or []
    if unknowns:
        logger.warning("Missing data for %s: %s", account_id, unknowns)
    logger.info("Demo stage complete for account %s", account_id)
    return memo


def main():
    parser = argparse.ArgumentParser(description="Extract account memo from demo transcript.")
    parser.add_argument("transcript", help="Path to demo call transcript file")
    parser.add_argument("--account-id", "-a", required=True, help="Account ID")
    parser.add_argument("--output", "-o", help="Output JSON path (default: stdout)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    memo = extract_demo_data(args.transcript, args.account_id)
    out = json.dumps(memo, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        logger.info("Output path written: %s", args.output)
    else:
        print(out)


if __name__ == "__main__":
    main()
