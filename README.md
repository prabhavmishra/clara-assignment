# Clara Answers – Zero-Cost Automation Pipeline

## How to Run
Clone the repo and run:
``bash
python3 scripts/run_pipeline.py

A **local, rule-based** pipeline that turns demo call and onboarding call transcripts into structured account memos and Retell agent specs, with versioning (v1 → v2) and changelog generation. No paid APIs; no hallucination of missing data.

---

## 1. Project overview

This project implements a **rule-based call-processing pipeline** for the Clara AI assignment. It:

- Runs **locally** with no paid APIs or LLM calls.
- Uses **regex and templating** only (deterministic, zero-cost).
- Produces **v1** agent specs from demo transcripts and **v2** agent specs after applying onboarding updates.
- Generates **field-level changelogs** (JSON and Markdown) between v1 and v2.

The system does not invent data; missing information is recorded in `questions_or_unknowns` and left empty where appropriate.

---

## 2. Architecture

- **Pipeline A (demo → v1):** Demo transcript → `extract_demo_data.py` → account memo v1 → `generate_agent_prompt.py` → Retell agent spec v1.
- **Pipeline B (onboarding → v2):** Onboarding transcript → `extract_onboarding_updates.py` → update patch → `apply_updates.py` → account memo v2 → `generate_agent_prompt.py` → Retell agent spec v2.
- **Changelog:** v1 memo + v2 memo and v1 spec + v2 spec → `changelog_utils.py` → field-level diff → `changelog/<account_id>_changelog.json` and `.md`.

All steps are orchestrated by a single script: `scripts/run_pipeline.py`.

---

## 3. Data flow

```
dataset/demo_calls/*.txt           →  extract_demo_data.py       →  account_memo (v1)
                                                                        ↓
                                    generate_agent_prompt.py     →  retell_agent_spec (v1)
                                                                        ↓
outputs/accounts/<account_id>/v1/   ←  account_memo.json, retell_agent_spec.json

dataset/onboarding_calls/*.txt     →  extract_onboarding_updates.py →  onboarding update patch
                                                                        ↓
                                    apply_updates.py (v1_memo + patch → v2_memo)
                                                                        ↓
                                    generate_agent_prompt.py     →  retell_agent_spec (v2)
                                                                        ↓
outputs/accounts/<account_id>/v2/  ←  account_memo.json, retell_agent_spec.json

v1 memo + v2 memo, v1 spec + v2 spec  →  changelog_utils.py  →  field-level diff
                                                                        ↓
changelog/                         ←  <account_id>_changelog.json, <account_id>_changelog.md
```

---

## 4. Folder structure

```
pipeline/
├── README.md
├── requirements.txt              # Optional; standard library only
├── schemas.py                    # Account memo & Retell spec structures
├── scripts/
│   ├── run_pipeline.py           # Orchestration: demo → v1; onboarding → v2; changelog
│   ├── extract_demo_data.py      # Demo transcript → account memo (v1)
│   ├── extract_onboarding_updates.py  # Onboarding transcript → updates patch
│   ├── apply_updates.py          # v1 memo + updates → v2 memo
│   ├── generate_agent_prompt.py  # Account memo → Retell agent spec
│   └── changelog_utils.py        # Diff v1 vs v2 → changelog JSON + MD
├── dataset/
│   ├── demo_calls/               # Demo call transcripts (e.g. demo_01.txt)
│   └── onboarding_calls/         # Onboarding call transcripts (e.g. onboarding_01.txt)
├── outputs/
│   └── accounts/
│       └── <account_id>/
│           ├── v1/
│           │   ├── account_memo.json
│           │   └── retell_agent_spec.json
│           └── v2/
│               ├── account_memo.json
│               └── retell_agent_spec.json
└── changelog/
    ├── <account_id>_changelog.json
    └── <account_id>_changelog.md
```

---

## 5. Automation orchestration

The entire pipeline is executed via a single orchestration script:

```bash
python3 scripts/run_pipeline.py
```

This script coordinates:

1. **Demo transcript extraction** – parse demo call → account memo v1  
2. **v1 account memo generation** – written to `outputs/accounts/<account_id>/v1/account_memo.json`  
3. **v1 agent specification generation** – written to `outputs/accounts/<account_id>/v1/retell_agent_spec.json`  
4. **Onboarding update extraction** – parse onboarding call → update patch  
5. **Memo update to v2** – apply patch to v1 memo → v2 memo  
6. **v2 agent specification generation** – written to `outputs/accounts/<account_id>/v2/retell_agent_spec.json`  
7. **Changelog generation** – field-level diff of v1 vs v2 memo and v1 vs v2 spec → `changelog/<account_id>_changelog.json` and `changelog/<account_id>_changelog.md`

The pipeline is designed to be:

- **Repeatable** – same inputs produce the same outputs  
- **Deterministic** – no LLM or non-deterministic steps  
- **Idempotent** – running it multiple times produces the same outputs  

---

## 6. How to run the pipeline

### Prerequisites

- **Python 3.10+** (standard library only; no external packages required).

### Add transcripts

- Put **demo** transcripts in `dataset/demo_calls/` (e.g. `demo_01.txt`, `demo_02.txt`).
- Put **onboarding** transcripts in `dataset/onboarding_calls/` (e.g. `onboarding_01.txt`, `onboarding_02.txt`).

Account IDs are derived from demo filenames (e.g. `demo_01.txt` → `account_01`). Onboarding files are paired by the same id segment (e.g. `01` in `onboarding_01.txt`).

### Full pipeline (demo + onboarding + changelog)

From the **project root** (`pipeline/`):

```bash
python3 scripts/run_pipeline.py
```

Expected results (for an account such as `account_01`):

- `outputs/accounts/account_01/v1/account_memo.json`
- `outputs/accounts/account_01/v1/retell_agent_spec.json`
- `outputs/accounts/account_01/v2/account_memo.json`
- `outputs/accounts/account_01/v2/retell_agent_spec.json`
- `changelog/account_01_changelog.json`
- `changelog/account_01_changelog.md`

### Demo-only mode

To run only the demo stage (v1 memo + v1 spec, no onboarding or changelog):

```bash
python3 scripts/run_pipeline.py --demo-only
```

### Custom paths and verbose logging

```bash
python3 scripts/run_pipeline.py --demo-dir ./dataset/demo_calls --onboarding-dir ./dataset/onboarding_calls --output-dir ./outputs/accounts --changelog-dir ./changelog
python3 scripts/run_pipeline.py --verbose
```

---

## 7. Demo-only mode

Use `--demo-only` when you have only demo transcripts and want v1 outputs only. The pipeline will:

- Process each demo in `dataset/demo_calls/`
- Write v1 memo and v1 Retell spec under `outputs/accounts/<account_id>/v1/`
- Skip onboarding extraction, v2 generation, and changelog

---

## 8. Limitations

- **Extraction:** Rule-based (regex/heuristics). Works best with consistent phrasing (e.g. “business hours 9 to 5”, “transfer to dispatch”). Unusual wording may be missed and appear in `questions_or_unknowns`.
- **Pairing:** Onboarding files are matched to accounts by a numeric/id segment in the filename. Different naming may require adjusting `derive_account_id` and pairing logic in `run_pipeline.discover_pairs`.
- **Retell:** This repo only produces **Retell agent spec JSON** files. It does not call the Retell API. Import the generated spec manually into Retell or add a separate step that uses the Retell API if you have access.
- **No LLMs:** All processing is local and deterministic; no paid APIs or LLM calls are used.

---

## Assignment requirements (summary)

- **Goal:** Demo call → preliminary Retell agent (v1); onboarding call → updated agent (v2) with clear changelog.
- **Constraints:** Zero spend, free-tier only, reproducible. No paid APIs.
- **Inputs:** Demo and onboarding call transcripts (e.g. 5 + 5 files). Transcripts are primary input (no transcription step).
- **Outputs:** Account memo JSON and Retell agent spec JSON per account/version; changelog (JSON + Markdown) with field-level diff.
- **Data discipline:** No hallucination. Missing information goes into `questions_or_unknowns`; extraction is rule-based.

---

## JSON schemas (summary)

- **Account memo:** See `schemas.empty_account_memo()` and `ACCOUNT_MEMO_FIELDS` in `schemas.py`.
- **Retell agent spec:** See `schemas.empty_retell_spec()`. Includes `version`, `agent_name`, `voice_style`, `system_prompt`, `key_variables`, `call_transfer_protocol`, `fallback_protocol_if_transfer_fails`, and internal-only `tool_invocation_placeholders`.
- **Changelog:** `account_id`, `from_version`, `to_version`, `memo_changes` (field, old_value, new_value), `spec_changes`, `summary`. Both JSON and Markdown formats are generated with field-level diff (e.g. “Field changed: business_hours / Old: Not specified / New: Mon-Fri 9am-5pm PST”).

---

## License and data

- Do not commit real customer PII. Treat provided transcripts as confidential.
- This project uses only the standard library and runs fully locally with no paid APIs.
