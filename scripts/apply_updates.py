#!/usr/bin/env python3
"""
Apply onboarding updates to v1 account memo to produce v2.
Merges only provided fields; does not overwrite with empty values.
"""

import argparse
import copy
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schemas import empty_account_memo, ACCOUNT_MEMO_FIELDS

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("apply_updates")


def _deep_merge(base: dict, updates: dict, exclude_keys: set = None) -> dict:
    """Merge updates into base. Empty strings/lists in updates do not overwrite."""
    exclude_keys = exclude_keys or {"_source"}
    result = copy.deepcopy(base)
    for k, v in updates.items():
        if k in exclude_keys:
            continue
        if v is None:
            continue
        if isinstance(v, dict) and k in result and isinstance(result[k], dict):
            result[k] = _deep_merge(result[k], v, exclude_keys)
        elif isinstance(v, list) and v:
            result[k] = v
        elif isinstance(v, str) and v.strip():
            result[k] = v.strip()
        elif isinstance(v, dict) and v != {}:
            result[k] = _deep_merge(result.get(k, {}), v, exclude_keys)
    return result


def apply_updates(v1_memo: dict, onboarding_updates: dict) -> dict:
    """
    Produce v2 memo by applying onboarding updates to v1.
    Preserves v1 fields where onboarding did not provide new values.
    """
    logger.info("Apply-updates stage starting (v1 memo + onboarding patch -> v2)")
    v2 = _deep_merge(v1_memo, onboarding_updates)
    v2["account_id"] = v1_memo.get("account_id", "")
    # Ensure questions_or_unknowns is refreshed: remove items that are now answered
    v2_unknowns = v2.get("questions_or_unknowns") or []
    if isinstance(v2_unknowns, list):
        v2["questions_or_unknowns"] = v2_unknowns
    v2["notes"] = (v2.get("notes") or "").strip() + " Updated from onboarding."
    logger.info("Apply-updates stage complete; v2 memo produced")
    return v2


def main():
    parser = argparse.ArgumentParser(description="Apply onboarding updates to v1 memo -> v2 memo.")
    parser.add_argument("v1_memo", help="Path to v1 account memo JSON")
    parser.add_argument("onboarding_updates", help="Path to onboarding updates JSON (from extract_onboarding_updates)")
    parser.add_argument("--output", "-o", required=True, help="Output v2 memo JSON path")
    args = parser.parse_args()

    v1 = json.loads(Path(args.v1_memo).read_text(encoding="utf-8"))
    updates = json.loads(Path(args.onboarding_updates).read_text(encoding="utf-8"))

    v2 = apply_updates(v1, updates)
    Path(args.output).write_text(json.dumps(v2, indent=2), encoding="utf-8")
    logger.info("Output path written: %s", args.output)


if __name__ == "__main__":
    main()
