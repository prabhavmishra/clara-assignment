#!/usr/bin/env python3
"""
Run the full pipeline: demo -> v1; onboarding -> v2 + changelog.
Batch processes all transcripts in dataset/demo_calls and dataset/onboarding_calls.
Pairs by account_id derived from filename (e.g. demo_01.txt / onboarding_01.txt -> account_01).
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, List

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from schemas import empty_account_memo

from extract_demo_data import extract_demo_data
from extract_onboarding_updates import extract_updates
from apply_updates import apply_updates
from generate_agent_prompt import memo_to_retell_spec
from changelog_utils import generate_changelog, write_changelog

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("pipeline")

# Default paths relative to project root
PROJECT_ROOT = _PROJECT_ROOT
DEFAULT_DEMO_DIR = PROJECT_ROOT / "dataset" / "demo_calls"
DEFAULT_ONBOARDING_DIR = PROJECT_ROOT / "dataset" / "onboarding_calls"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "accounts"
DEFAULT_CHANGELOG_DIR = PROJECT_ROOT / "changelog"

# Filename pattern: demo_01.txt, onboarding_01.txt -> account_id = account_01
ACCOUNT_ID_PATTERN = re.compile(r"(?:demo|onboarding)[_\s\-]*(\w+)", re.I)


def derive_account_id(filename: str, prefix: str = "account_") -> str:
    base = Path(filename).stem
    # Prefer numeric suffix (e.g. demo_01 -> 01) for pairing with onboarding_01
    m = re.search(r"[\_\-\s](\d+)$", base) or re.search(r"(\d+)", base)
    if m:
        return f"{prefix}{m.group(1)}"
    m = re.search(r"[\_\-\s](\w+)$", base)
    if m:
        return f"{prefix}{m.group(1)}"
    return f"{prefix}{base.replace(' ', '_')}"


def discover_pairs(demo_dir: Path, onboarding_dir: Path) -> List[Tuple[str, Path, Optional[Path]]]:
    """
    Discover (account_id, demo_path, onboarding_path) pairs.
    Demo and onboarding files are matched by numeric/same suffix (e.g. 01, 02).
    """
    demo_dir = Path(demo_dir)
    onboarding_dir = Path(onboarding_dir)
    demo_dir.mkdir(parents=True, exist_ok=True)
    onboarding_dir.mkdir(parents=True, exist_ok=True)

    demos = {}
    for f in demo_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".txt", ".json", ".md"):
            aid = derive_account_id(f.name)
            demos[aid] = f

    pairs = []
    for aid, demo_path in demos.items():
        # Match onboarding by same id segment (e.g. account_01 -> 01 -> onboarding_01.txt)
        id_suffix = aid.replace("account_", "") if aid.startswith("account_") else aid
        onboarding_path = None
        for f in onboarding_dir.iterdir():
            if not f.is_file() or f.suffix.lower() not in (".txt", ".json", ".md"):
                continue
            if id_suffix in f.stem or f.stem.endswith("_" + id_suffix):
                onboarding_path = f
                break
        if not onboarding_path and onboarding_dir.exists():
            used = {p[2] for p in pairs if p[2]}
            for f in onboarding_dir.iterdir():
                if f.is_file() and f not in used:
                    onboarding_path = f
                    break
        pairs.append((aid, demo_path, onboarding_path))
    return pairs


def _memo_has_required_fields(memo: dict) -> bool:
    """Ensure memo has minimal fields needed for agent prompt generation."""
    return isinstance(memo, dict) and "account_id" in memo


def run_demo_only(account_id: str, demo_path: Path, output_root: Path) -> tuple[Path, Path]:
    """Run Pipeline A: demo -> v1 memo + v1 spec."""
    v1_dir = output_root / account_id / "v1"
    v1_dir.mkdir(parents=True, exist_ok=True)
    memo_path = v1_dir / "account_memo.json"
    spec_path = v1_dir / "retell_agent_spec.json"

    logger.info("Processing account %s", account_id)
    memo = extract_demo_data(str(demo_path), account_id)
    if not _memo_has_required_fields(memo):
        logger.warning("Memo missing required fields for %s; generating spec anyway", account_id)
    spec = memo_to_retell_spec(memo, version="v1")
    logger.info("Generated v1 agent spec for %s", account_id)

    memo_path.write_text(json.dumps(memo, indent=2), encoding="utf-8")
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    logger.info("Output paths written: %s, %s", memo_path, spec_path)
    return memo_path, spec_path


def run_onboarding(
    account_id: str,
    onboarding_path: Path,
    v1_memo_path: Path,
    v1_spec_path: Path,
    output_root: Path,
    changelog_dir: Path,
) -> None:
    """Run Pipeline B: onboarding -> v2 memo + v2 spec + changelog."""
    logger.info("Onboarding stage for account %s", account_id)
    v1_memo = json.loads(v1_memo_path.read_text(encoding="utf-8"))
    v1_spec = json.loads(v1_spec_path.read_text(encoding="utf-8"))

    updates = extract_updates(str(onboarding_path))
    v2_memo = apply_updates(v1_memo, updates)
    if not _memo_has_required_fields(v2_memo):
        logger.warning("v2 memo missing required fields for %s; generating spec anyway", account_id)
    v2_spec = memo_to_retell_spec(v2_memo, version="v2")
    logger.info("Generated v2 agent spec for %s", account_id)

    v2_dir = output_root / account_id / "v2"
    v2_dir.mkdir(parents=True, exist_ok=True)
    v2_memo_path = v2_dir / "account_memo.json"
    v2_spec_path = v2_dir / "retell_agent_spec.json"

    v2_memo_path.write_text(json.dumps(v2_memo, indent=2), encoding="utf-8")
    v2_spec_path.write_text(json.dumps(v2_spec, indent=2), encoding="utf-8")
    logger.info("Output paths written: %s, %s", v2_memo_path, v2_spec_path)

    cl = generate_changelog(v1_memo, v2_memo, v1_spec, v2_spec)
    changelog_dir.mkdir(parents=True, exist_ok=True)
    write_changelog(cl, changelog_dir / f"{account_id}_changelog", format="both")
    logger.info("Changelog written: %s", changelog_dir / f"{account_id}_changelog")


def run_pipeline(
    demo_dir: Path = DEFAULT_DEMO_DIR,
    onboarding_dir: Path = DEFAULT_ONBOARDING_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    changelog_dir: Path = DEFAULT_CHANGELOG_DIR,
    demo_only: bool = False,
) -> None:
    demo_dir = Path(demo_dir)
    onboarding_dir = Path(onboarding_dir)
    output_dir = Path(output_dir)
    changelog_dir = Path(changelog_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    changelog_dir.mkdir(parents=True, exist_ok=True)

    pairs = discover_pairs(demo_dir, onboarding_dir)
    if not pairs:
        logger.warning("No demo files found in %s. Add transcripts to run.", demo_dir)
        return

    for account_id, demo_path, onboarding_path in pairs:
        try:
            if not demo_path.exists():
                logger.warning("Demo transcript missing for %s: %s; skipping", account_id, demo_path)
                continue
            run_demo_only(account_id, demo_path, output_dir)
            if demo_only:
                continue
            if not onboarding_path or not onboarding_path.exists():
                logger.info("No onboarding transcript for %s; v1 only.", account_id)
                continue
            v1_memo = output_dir / account_id / "v1" / "account_memo.json"
            v1_spec = output_dir / account_id / "v1" / "retell_agent_spec.json"
            if not v1_memo.exists() or not v1_spec.exists():
                logger.warning("v1 outputs not found for %s; skipping onboarding", account_id)
                continue
            run_onboarding(account_id, onboarding_path, v1_memo, v1_spec, output_dir, changelog_dir)
        except Exception as e:
            logger.exception("Pipeline failed for %s: %s", account_id, e)
            raise


def main():
    parser = argparse.ArgumentParser(description="Run demo -> v1; onboarding -> v2 + changelog (batch).")
    parser.add_argument("--demo-dir", default=DEFAULT_DEMO_DIR, type=Path, help="Directory of demo transcripts")
    parser.add_argument("--onboarding-dir", default=DEFAULT_ONBOARDING_DIR, type=Path, help="Directory of onboarding transcripts")
    parser.add_argument("--output-dir", "-o", default=DEFAULT_OUTPUT_DIR, type=Path, help="Output root (outputs/accounts)")
    parser.add_argument("--changelog-dir", default=DEFAULT_CHANGELOG_DIR, type=Path, help="Changelog output directory")
    parser.add_argument("--demo-only", action="store_true", help="Only run demo -> v1 (no onboarding)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run_pipeline(
        demo_dir=args.demo_dir,
        onboarding_dir=args.onboarding_dir,
        output_dir=args.output_dir,
        changelog_dir=args.changelog_dir,
        demo_only=args.demo_only,
    )
    logger.info("Pipeline complete.")


if __name__ == "__main__":
    main()
