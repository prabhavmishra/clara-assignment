"""
Changelog generation: diff v1 vs v2 memo and agent spec, produce structured changelog.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("changelog")


def _diff_value(old: Any, new: Any) -> bool:
    if old != new:
        return True
    return False


def _collect_diffs(obj1: dict, obj2: dict, prefix: str = "") -> list:
    changes = []
    all_keys = set(obj1.keys()) | set(obj2.keys())
    for k in all_keys:
        if k.startswith("_"):
            continue
        key_path = f"{prefix}.{k}" if prefix else k
        v1 = obj1.get(k)
        v2 = obj2.get(k)
        if isinstance(v1, dict) and isinstance(v2, dict):
            changes.extend(_collect_diffs(v1, v2, key_path))
        elif _diff_value(v1, v2):
            changes.append({
                "field": key_path,
                "old_value": v1,
                "new_value": v2,
            })
    return changes


def generate_changelog(v1_memo: dict, v2_memo: dict, v1_spec: dict = None, v2_spec: dict = None) -> dict:
    memo_changes = _collect_diffs(v1_memo, v2_memo)
    spec_changes = _collect_diffs(v1_spec or {}, v2_spec or {}) if (v1_spec or v2_spec) else []
    return {
        "account_id": v2_memo.get("account_id") or v1_memo.get("account_id"),
        "from_version": "v1",
        "to_version": "v2",
        "memo_changes": memo_changes,
        "spec_changes": spec_changes,
        "summary": f"{len(memo_changes)} memo field(s) changed, {len(spec_changes)} spec field(s) changed.",
    }


def write_changelog(changelog: dict, path: Path, format: str = "both") -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if format in ("json", "both"):
        json_path = path if path.suffix == ".json" else path.with_suffix(".json")
        json_path.write_text(json.dumps(changelog, indent=2), encoding="utf-8")
        logger.info("Wrote changelog JSON: %s", json_path)
    if format in ("md", "both"):
        md_path = path if path.suffix == ".md" else path.with_suffix(".md")
        md_content = _changelog_to_md(changelog)
        md_path.write_text(md_content, encoding="utf-8")
        logger.info("Wrote changelog MD: %s", md_path)


def _changelog_to_md(cl: dict) -> str:
    lines = [
        f"# Changelog: {cl.get('account_id', 'unknown')}",
        f"**{cl.get('from_version', 'v1')} → {cl.get('to_version', 'v2')}**",
        "",
        cl.get("summary", ""),
        "",
        "## Account memo changes (field-level diff)",
        "",
    ]
    for c in cl.get("memo_changes", []):
        old_str = _repr(c.get("old_value"))
        new_str = _repr(c.get("new_value"))
        if not old_str:
            old_str = "Not specified"
        if not new_str:
            new_str = "Not specified"
        lines.append(f"**Field changed:** {c['field']}")
        lines.append(f"- Old: {old_str}")
        lines.append(f"- New: {new_str}")
        lines.append("")
    lines.append("## Agent spec changes (field-level diff)")
    lines.append("")
    for c in cl.get("spec_changes", []):
        old_str = _repr(c.get("old_value"))
        new_str = _repr(c.get("new_value"))
        if not old_str:
            old_str = "Not specified"
        if not new_str:
            new_str = "Not specified"
        lines.append(f"**Field changed:** {c['field']}")
        lines.append(f"- Old: {old_str}")
        lines.append(f"- New: {new_str}")
        lines.append("")
    return "\n".join(lines)


def _repr(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (list, dict)):
        return json.dumps(v)[:200]
    return str(v)[:200]
