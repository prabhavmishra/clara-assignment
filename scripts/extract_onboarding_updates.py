#!/usr/bin/env python3
"""
Extract updates/patch from onboarding call transcript (rule-based).
Output is a partial structure that apply_updates can merge into v1 memo.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import empty_account_memo

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("extract_onboarding")

# Reuse similar patterns as demo; onboarding often has clearer, final values
BUSINESS_HOURS_DAYS = re.compile(
    r"(?:mon(?:day)?|tue(?:s)?|wed(?:nesday)?|thu(?:rs)?|fri(?:day)?|sat(?:urday)?|sun(?:day)?)"
    r"(?:\s*[-–to]+\s*(?:mon|tue|wed|thu|fri|sat|sun))?",
    re.I,
)
BUSINESS_HOURS_TIME = re.compile(
    r"(?:hours?|open|business\s+hours?)\s*(?:are|:)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s*(?:[-–to]\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?",
    re.I,
)
TIMEZONE_PATTERN = re.compile(
    r"\b(EST|EDT|CST|CDT|MST|MDT|PST|PDT|Eastern|Central|Mountain|Pacific|UTC[-+]?\d*)\b",
    re.I,
)

ADDRESS_PATTERNS = [
    re.compile(r"(?:address|located at|office at)\s*[:\-]?\s*([0-9]+\s+[A-Za-z0-9\s,\.\-]+(?:street|st|ave|avenue|blvd|road|rd|drive|dr)[A-Za-z0-9\s,\.\-]*)", re.I),
    re.compile(r"(\d{1,6}\s+[\w\s]+(?:street|st|ave|blvd|road|rd|drive|dr)\.?\s*[^\n]{0,80})", re.I),
]

EMERGENCY_KEYWORDS = [
    "sprinkler leak", "fire", "alarm", "emergency", "urgent", "water leak",
    "life safety", "extinguisher",
]

ROUTING_PATTERNS = [
    re.compile(r"(?:all\s+)?emergency\s+(?:sprinkler\s+)?calls?\s+(?:must\s+)?(?:go\s+)?(?:directly\s+)?(?:to\s+)?([^\n\.]+?)(?:\.|$)", re.I),
    re.compile(r"(?:transfer|route|send)\s+(?:calls?|to)\s+(?:the\s+)?([^\n\.]+?)(?:\.|,|$)", re.I),
    re.compile(r"(?:after\s+hours?|afterhours?)\s+(?:we\s+)?(?:transfer|route|send)\s+to\s+([^\n\.]+)", re.I),
    re.compile(r"phone\s+tree", re.I),
]

INTEGRATION_PATTERNS = [
    re.compile(r"never\s+create\s+([^\n\.]+?)\s+in\s+ServiceTrade", re.I),
    re.compile(r"(?:never|don't|do not)\s+([^\n\.]*ServiceTrade[^\n\.]*)", re.I),
]

TRANSFER_TIMEOUT = re.compile(r"(?:timeout|after)\s+(?:transfer\s+)?(\d+)\s*(?:sec|second|min|minute)", re.I)
TRANSFER_RETRIES = re.compile(r"(?:retry|retries?)\s*(?:of\s*)?(\d+)", re.I)
FALLBACK_60 = re.compile(r"if\s+transfer\s+fails\s+(?:after\s+)?(\d+)\s*sec", re.I)


def extract_updates(transcript_path: str) -> dict:
    """Return a sparse dict with only fields that were found (to be merged by apply_updates)."""
    path = Path(transcript_path)
    if not path.exists():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    logger.info("Onboarding stage starting: %s", transcript_path)
    text = path.read_text(encoding="utf-8", errors="replace")
    logger.info("Onboarding transcript parsed: %s", transcript_path)

    updates = {}
    # Business hours
    bh = {"days": [], "start": "", "end": "", "timezone": ""}
    for m in BUSINESS_HOURS_DAYS.finditer(text):
        d = m.group(0).strip()
        if d and d not in bh["days"]:
            bh["days"].append(d)
    m = BUSINESS_HOURS_TIME.search(text)
    if m:
        bh["start"] = (m.group(1) or "").strip()
        bh["end"] = (m.group(2) or "").strip()
    tz = TIMEZONE_PATTERN.search(text)
    if tz:
        bh["timezone"] = tz.group(1).strip()
    if any(bh.values()) or bh["days"]:
        updates["business_hours"] = bh

    # Address
    for pat in ADDRESS_PATTERNS:
        m = pat.search(text)
        if m:
            updates["office_address"] = m.group(1).strip()[:200]
            break

    # Emergency definition
    found_emergency = []
    lower = text.lower()
    for s in EMERGENCY_KEYWORDS:
        if s.lower() in lower and s not in found_emergency:
            found_emergency.append(s)
    if found_emergency:
        updates["emergency_definition"] = found_emergency

    # Routing
    rules = []
    for pat in ROUTING_PATTERNS:
        if pat.groups == 0:
            if pat.search(text):
                rules.append("Use phone tree / follow routing discussed.")
        else:
            for m in pat.finditer(text):
                r = m.group(1).strip() if m.lastindex else "phone tree"
                if r and len(r) < 200 and r not in rules:
                    rules.append(r)
    if rules:
        updates["emergency_routing_rules"] = rules

    # Integration
    constraints = []
    for pat in INTEGRATION_PATTERNS:
        for m in pat.finditer(text):
            c = m.group(1).strip() if m.lastindex else m.group(0).strip()
            if c and c not in constraints:
                constraints.append(c[:200])
    if constraints:
        updates["integration_constraints"] = constraints

    # Transfer rules
    tr = {}
    m = TRANSFER_TIMEOUT.search(text) or FALLBACK_60.search(text)
    if m:
        tr["timeouts"] = m.group(1) + " seconds"
    m = TRANSFER_RETRIES.search(text)
    if m:
        tr["retries"] = m.group(1)
    if "if transfer fails" in lower or "when transfer fails" in lower:
        idx = lower.find("if transfer fails")
        if idx == -1:
            idx = lower.find("when transfer fails")
        tr["if_fails_say"] = text[idx : idx + 200].strip()[:150]
    if tr:
        updates["call_transfer_rules"] = tr

    updates["_source"] = "onboarding_transcript"
    logger.info("Onboarding stage complete; extracted %s field(s)", len([k for k in updates if not k.startswith("_")]))
    return updates


def main():
    parser = argparse.ArgumentParser(description="Extract onboarding updates from transcript.")
    parser.add_argument("transcript", help="Path to onboarding transcript file")
    parser.add_argument("--output", "-o", help="Output JSON path (default: stdout)")
    args = parser.parse_args()

    updates = extract_updates(args.transcript)
    out = json.dumps(updates, indent=2)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
        logger.info("Output path written: %s", args.output)
    else:
        print(out)


if __name__ == "__main__":
    main()
