# Setup & Deployment Guide

## Quick Start

### Prerequisites

- Python 3.10+ (standard library only, no external packages)
- Git (for cloning and version control)
- Optional: n8n (Docker required for local deployment)

### 1. Clone the Repository

```bash
git clone https://github.com/prabhavmishra/clara-assignment.git
cd clara-assignment
```

### 2. Prepare Your Datasets

Add your transcript files:

```bash
# Place demo call transcripts here
cp /path/to/demo_calls/*.txt dataset/demo_calls/

# Place onboarding call transcripts here
cp /path/to/onboarding_calls/*.txt dataset/onboarding_calls/
```

**Naming Convention:**
- Demo files: `demo_01.txt`, `demo_02.txt`, ... `demo_05.txt`
- Onboarding files: `onboarding_01.txt`, `onboarding_02.txt`, ... `onboarding_05.txt`

The pipeline pairs them by the numeric suffix automatically.

### 3. Run the Pipeline

From the project root:

```bash
python3 scripts/run_pipeline.py
```

**Expected Output:**
```
INFO [pipeline] Processing account account_01
INFO [extract_demo] Demo stage starting for account account_01
INFO [extract_demo] Demo stage complete for account account_01
INFO [pipeline] Generated v1 agent spec for account_01
INFO [pipeline] Onboarding stage for account account_01
INFO [extract_onboarding] Onboarding stage complete; extracted 6 field(s)
INFO [apply_updates] Apply-updates stage complete; v2 memo produced
INFO [pipeline] Generated v2 agent spec for account_01
INFO [changelog] Wrote changelog JSON: ./changelog/account_01_changelog.json
INFO [pipeline] Pipeline complete.
```

### 4. View Outputs

**Account 01 outputs:**
```
outputs/accounts/account_01/v1/account_memo.json
outputs/accounts/account_01/v1/retell_agent_spec.json
outputs/accounts/account_01/v2/account_memo.json
outputs/accounts/account_01/v2/retell_agent_spec.json
changelog/account_01_changelog.json
changelog/account_01_changelog.md
```

### 5. (Optional) Deploy with n8n

If you want to orchestrate via n8n instead of running Python directly:

```bash
# Install Docker if you don't have it
# https://docs.docker.com/get-docker/

# Create a docker-compose.yml for n8n
docker-compose up -d

# Import the workflow
# 1. Open http://localhost:5678
# 2. Import workflow from: n8n-workflow-export.json
# 3. Configure trigger to watch dataset/demo_calls/
# 4. Set up error handling and notifications (optional)
```

See [N8N_DEPLOYMENT.md](#) for detailed steps.

---

## Architecture

### Data Flow

```
Demo Call Transcripts
    ↓
extract_demo_data.py (rule-based regex)
    ↓
v1 Account Memo (JSON)
    ↓
generate_agent_prompt.py (templating)
    ↓
v1 Retell Agent Spec (JSON)
    ↓
[Stored in outputs/accounts/<account_id>/v1/]

Onboarding Call Transcripts
    ↓
extract_onboarding_updates.py (sparse patch)
    ↓
Update Patch (JSON)
    ↓
apply_updates.py (deep merge v1 + patch)
    ↓
v2 Account Memo (JSON)
    ↓
generate_agent_prompt.py (templating)
    ↓
v2 Retell Agent Spec (JSON)
    ↓
[Stored in outputs/accounts/<account_id>/v2/]

v1 + v2 Memo & Spec
    ↓
changelog_utils.py (field-level diff)
    ↓
Changelog (JSON + Markdown)
    ↓
[Stored in changelog/<account_id>_changelog.*]
```

### Module Responsibilities

| Module | Input | Output | Purpose |
|--------|-------|--------|---------|
| `extract_demo_data.py` | Demo transcript (`.txt`) | Account memo v1 (`.json`) | Parse demo call; extract company, hours, services, routing |
| `extract_onboarding_updates.py` | Onboarding transcript (`.txt`) | Update patch (`.json`) | Parse onboarding call; extract changed fields only |
| `apply_updates.py` | v1 memo + update patch | v2 memo (`.json`) | Merge v1 + onboarding patch → v2 |
| `generate_agent_prompt.py` | Account memo | Retell agent spec (`.json`) | Generate system prompt + key variables for Retell |
| `changelog_utils.py` | v1 + v2 memo/spec | Changelog (`.json`, `.md`) | Diff and format changes between versions |
| `run_pipeline.py` | Transcripts from `dataset/` | All above outputs | Orchestrate all steps; batch process accounts |
| `schemas.py` | (internal) | JSON schema definitions | Define account memo and agent spec structure |

---

## Configuration

### Environment Variables

Optional: Set these in a `.env` file or pass as command-line arguments:

```bash
# .env file
DEMO_CALLS_DIR=./dataset/demo_calls
ONBOARDING_CALLS_DIR=./dataset/onboarding_calls
OUTPUT_DIR=./outputs/accounts
CHANGELOG_DIR=./changelog
LOG_LEVEL=INFO
```

### Command-Line Options

```bash
# Run with custom paths
python3 scripts/run_pipeline.py \
  --demo-dir ./dataset/demo_calls \
  --onboarding-dir ./dataset/onboarding_calls \
  --output-dir ./outputs/accounts \
  --changelog-dir ./changelog \
  --verbose

# Demo-only mode (skip onboarding)
python3 scripts/run_pipeline.py --demo-only

# Specific account only
python3 scripts/run_pipeline.py --account-id account_01
```

---

## File Structure

After running the pipeline with 5 demo + 5 onboarding files:

```
clara-assignment/
├── README.md                                 # Main project documentation
├── RETELL_INTEGRATION.md                     # How to use outputs in Retell
├── SETUP_DEPLOYMENT.md                       # This file
├── schemas.py                                # JSON schema definitions
├── requirements.txt                          # (empty; std lib only)
├── n8n-workflow-export.json                  # n8n workflow export
├── .gitignore                                # Ignore outputs/ and changelog/
├── .git/                                     # Git repository
│
├── scripts/
│   ├── run_pipeline.py                       # Main orchestration
│   ├── extract_demo_data.py                  # Demo extraction
│   ├── extract_onboarding_updates.py         # Onboarding extraction
│   ├── apply_updates.py                      # Merge logic
│   ├── generate_agent_prompt.py              # Prompt generation
│   └── changelog_utils.py                    # Diff generation
│
├── dataset/
│   ├── demo_calls/
│   │   ├── demo_01.txt
│   │   ├── demo_02.txt
│   │   ├── ...
│   │   └── demo_05.txt
│   └── onboarding_calls/
│       ├── onboarding_01.txt
│       ├── onboarding_02.txt
│       ├── ...
│       └── onboarding_05.txt
│
├── outputs/
│   └── accounts/
│       ├── account_01/
│       │   ├── v1/
│       │   │   ├── account_memo.json
│       │   │   └── retell_agent_spec.json
│       │   └── v2/
│       │       ├── account_memo.json
│       │       └── retell_agent_spec.json
│       ├── account_02/
│       │   ├── v1/
│       │   │   ├── account_memo.json
│       │   │   └── retell_agent_spec.json
│       │   └── v2/
│       │       ├── account_memo.json
│       │       └── retell_agent_spec.json
│       └── ... (accounts 3-5)
│
└── changelog/
    ├── account_01_changelog.json
    ├── account_01_changelog.md
    ├── account_02_changelog.json
    ├── account_02_changelog.md
    └── ... (changelogs 3-5)
```

---

## Testing

### Unit Test: Individual Modules

```bash
# Test demo extraction on a single file
python3 scripts/extract_demo_data.py dataset/demo_calls/demo_01.txt -o /tmp/test_memo.json
cat /tmp/test_memo.json

# Test onboarding extraction
python3 scripts/extract_onboarding_updates.py dataset/onboarding_calls/onboarding_01.txt -o /tmp/test_updates.json
cat /tmp/test_updates.json

# Test prompt generation
python3 scripts/generate_agent_prompt.py /tmp/test_memo.json --version v1 -o /tmp/test_spec.json
cat /tmp/test_spec.json

# Test changelog generation
python3 scripts/changelog_utils.py --v1-memo /tmp/test_memo.json --v2-memo /tmp/test_memo.json --output /tmp/test_changelog
```

### Integration Test: Full Pipeline

```bash
# Clean previous outputs
rm -rf outputs changelog

# Run full pipeline
python3 scripts/run_pipeline.py --verbose

# Verify outputs exist
ls -la outputs/accounts/account_01/v1/
ls -la outputs/accounts/account_01/v2/
cat changelog/account_01_changelog.md
```

### Validation Checklist

After running the pipeline, verify:

- [ ] Account memos are valid JSON
- [ ] Agent specs include system prompt and key variables
- [ ] Changelog shows field-level changes
- [ ] No "hallucinated" data (missing fields marked in `questions_or_unknowns`)
- [ ] Business hours and emergency routing are populated correctly
- [ ] Transfer fallback protocol is included in agent spec

---

## Logging & Debugging

### Enable Verbose Logging

```bash
python3 scripts/run_pipeline.py --verbose
```

### Check Logs for Errors

```bash
# View full output with timestamps
python3 scripts/run_pipeline.py 2>&1 | tee pipeline_run.log

# Filter for warnings/errors only
python3 scripts/run_pipeline.py 2>&1 | grep -E "WARNING|ERROR"
```

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Account memo incomplete" | Missing field in transcript | Check `questions_or_unknowns` in output JSON |
| "No onboarding file found" | Filename doesn't match pattern | Ensure `onboarding_01.txt` pairs with `demo_01.txt` |
| "Timezone not recognized" | Unusual timezone format in transcript | Add to `TIMEZONE_PATTERN` in `extract_demo_data.py` |
| "Prompt too long for Retell" | System prompt exceeds character limit | Use shorter descriptions in output JSON |
| "FileNotFoundError" | Missing transcript files | Verify `dataset/demo_calls/` and `dataset/onboarding_calls/` exist |

---

## Production Considerations

### For Real Customer Data

1. **PII Handling:**
   - Do not commit customer names, phone numbers, or addresses to git
   - Use `.gitignore` to exclude outputs with real data
   - Store outputs in a secure location (S3, Vault, Secured Folder)

2. **Scalability:**
   - For > 100 accounts, consider batch processing or queue
   - Monitor disk space for large outputs
   - Add database layer (SQLite, PostgreSQL) for query and versioning

3. **Error Handling:**
   - Implement retry logic for failed extractions
   - Add alerts for malformed transcripts
   - Create manual review queue for edge cases

4. **Version Control:**
   - Tag releases (v1.0, v1.1, v2.0) for each improvement
   - Document all changes to extraction logic
   - Maintain change history in CHANGELOG.md

5. **Integrations:**
   - Add Retell API calls (when free tier available)
   - Integrate task tracker (Asana, Monday.com free tier)
   - Add Slack notifications for pipeline completion

---

## Next Steps

1. **Test locally** with provided sample transcripts
2. **Import agent specs into Retell** (see [RETELL_INTEGRATION.md](./RETELL_INTEGRATION.md))
3. **Deploy with n8n** (optional; see n8n docs)
4. **Add real transcripts** and iterate
5. **Create Loom video** showing pipeline in action

---

## Support & Questions

- **README.md** – Full project overview and architecture
- **RETELL_INTEGRATION.md** – Retell setup and manual import steps
- **schemas.py** – JSON structure definitions
- **scripts/** – Code comments and docstrings

For issues, create a GitHub issue in the repository.
