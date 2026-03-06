# n8n Workflow Deployment Guide

## Overview

This guide shows how to deploy the Clara AI pipeline using **n8n** – a free, open-source workflow automation platform. With n8n, you can:

- Trigger the pipeline automatically when new transcripts arrive
- Monitor pipeline execution with a visual dashboard
- Retry failed runs without manual intervention
- Add notifications (Slack, email, webhook)

**Cost:** Free (self-hosted via Docker)

---

## Prerequisites

1. **Docker** installed ([download](https://docs.docker.com/get-docker/))
2. **Docker Compose** (included with Docker Desktop)
3. **Git** (to clone this repository)
4. **Python 3.10+** (for the Clara AI scripts)

---

## Step 1: Start n8n Locally

### Option A: Using Docker Compose (Recommended)

Create a `docker-compose.yml` in the project root:

```yaml
version: '3.8'

services:
  n8n:
    image: n8nio/n8n:latest
    container_name: clara-n8n
    ports:
      - "5678:5678"
    environment:
      - N8N_HOST=localhost
      - N8N_PORT=5678
      - N8N_PROTOCOL=http
      - WEBHOOK_TUNNEL_URL=http://localhost:5678/
      - GENERIC_TIMEZONE=America/New_York
    volumes:
      - n8n_data:/home/node/.n8n
      - ./dataset:/dataset
      - ./outputs:/outputs
      - ./changelog:/changelog
    networks:
      - n8n-net

volumes:
  n8n_data:

networks:
  n8n-net:
    driver: bridge
```

Start n8n:

```bash
docker-compose up -d
```

Access the dashboard:
- **URL:** http://localhost:5678
- **First run:** Set up admin credentials
- **Wait:** 30-60 seconds for initialization

### Option B: Local n8n Installation

```bash
# Install n8n globally (requires Node.js 18+)
npm install -g n8n

# Start n8n
n8n start

# Access: http://localhost:5678
```

---

## Step 2: Import the Workflow

### Method 1: Import from File (Recommended)

1. Open http://localhost:5678
2. Go to **Workflows** → **Import from file**
3. Select `n8n-workflow-export.json` from this repository
4. Click **Import**
5. Review the workflow DAG (visual representation)

### Method 2: Manual Recreation

If import fails, recreate manually:

1. Click **+ New Workflow**
2. Name it: `Clara AI - Demo to Onboarding Pipeline`
3. Add nodes in order (see below)

---

## Step 3: Configure Workflow Nodes

### Node 1: Trigger – Watch Dataset Directory

```
Node Type: File System Trigger
Event: On File Created/Modified
Path: /dataset/demo_calls/
File Pattern: *.txt
```

Configuration:
- **Poll Interval:** 30 seconds
- **Include:** Only `.txt` files
- **Trigger Once:** No (trigger on each change)

### Node 2: Extract Demo Data

```
Node Type: Execute Command
Command: python3 scripts/extract_demo_data.py {{ $node["File System Trigger"].data.path }} -o /tmp/demo_v1_memo.json
Working Directory: /path/to/clara-assignment/
```

### Node 3: Generate v1 Agent Spec

```
Node Type: Execute Command
Command: python3 scripts/generate_agent_prompt.py /tmp/demo_v1_memo.json --version v1 -o /tmp/demo_v1_spec.json
Working Directory: /path/to/clara-assignment/
```

### Node 4: Store v1 Outputs

```
Node Type: Execute Command
Command: |
  ACCOUNT_ID=$(cat /tmp/demo_v1_memo.json | jq -r .account_id)
  mkdir -p /outputs/accounts/$ACCOUNT_ID/v1
  cp /tmp/demo_v1_memo.json /outputs/accounts/$ACCOUNT_ID/v1/account_memo.json
  cp /tmp/demo_v1_spec.json /outputs/accounts/$ACCOUNT_ID/v1/retell_agent_spec.json
Working Directory: /path/to/clara-assignment/
```

### Node 5: Find Paired Onboarding File

```
Node Type: File System
Operation: List Files
Path: /dataset/onboarding_calls/
Filter: onboarding_{{ extract demo file number }}.txt
```

### Node 6: Extract Onboarding Updates

```
Node Type: Execute Command
Command: python3 scripts/extract_onboarding_updates.py {{ $node["Find Paired Onboarding"].data.path }} -o /tmp/onboarding_updates.json
Working Directory: /path/to/clara-assignment/
```

### Node 7: Apply Updates (v1 → v2)

```
Node Type: Execute Command
Command: python3 scripts/apply_updates.py /tmp/demo_v1_memo.json /tmp/onboarding_updates.json -o /tmp/v2_memo.json
Working Directory: /path/to/clara-assignment/
```

### Node 8: Generate v2 Agent Spec

```
Node Type: Execute Command
Command: python3 scripts/generate_agent_prompt.py /tmp/v2_memo.json --version v2 -o /tmp/v2_spec.json
Working Directory: /path/to/clara-assignment/
```

### Node 9: Generate Changelog

```
Node Type: Execute Command
Command: |
  ACCOUNT_ID=$(cat /tmp/v2_memo.json | jq -r .account_id)
  python3 scripts/changelog_utils.py \
    --v1-memo /tmp/demo_v1_memo.json \
    --v2-memo /tmp/v2_memo.json \
    --v1-spec /tmp/demo_v1_spec.json \
    --v2-spec /tmp/v2_spec.json \
    --output /changelog/$ACCOUNT_ID\_changelog
Working Directory: /path/to/clara-assignment/
```

### Node 10: Store v2 Outputs

```
Node Type: Execute Command
Command: |
  ACCOUNT_ID=$(cat /tmp/v2_memo.json | jq -r .account_id)
  mkdir -p /outputs/accounts/$ACCOUNT_ID/v2
  cp /tmp/v2_memo.json /outputs/accounts/$ACCOUNT_ID/v2/account_memo.json
  cp /tmp/v2_spec.json /outputs/accounts/$ACCOUNT_ID/v2/retell_agent_spec.json
Working Directory: /path/to/clara-assignment/
```

### Node 11: Notify Completion (Optional)

```
Node Type: Send Slack Message
Channel: #pipeline-alerts
Message: ✅ Pipeline complete for {{ $node["Store v2 Outputs"].data.account_id }}
          v1 and v2 outputs ready in /outputs/
```

(Requires Slack webhook integration)

---

## Step 4: Connect Nodes

In the n8n editor, connect nodes in sequence:

```
Trigger → Extract Demo
       ↓
Generate v1 Spec
       ↓
Store v1 Outputs
       ↓
Find Onboarding
       ↓
Extract Onboarding
       ↓
Apply Updates
       ↓
Generate v2 Spec
       ↓
Generate Changelog
       ↓
Store v2 Outputs
       ↓
[Optional] Notify
```

---

## Step 5: Configure Error Handling

### Global Error Handler

1. Right-click workflow canvas → **Workflow settings**
2. **Error handling:** Enable
3. Add retry logic:
   - **Max retries:** 2
   - **Retry interval:** 5 seconds

### Per-Node Error Handling

1. Right-click each node → **Settings**
2. **On Error:** Choose action:
   - `Continue` – Skip and move to next node
   - `Pause execution` – Stop and alert
   - `Execute workflow` – Run error handler workflow

---

## Step 6: Test the Workflow

### Manual Test (Single Account)

1. Copy a test transcript to `dataset/demo_calls/`:
   ```bash
   cp dataset/demo_calls/demo_01.txt dataset/demo_calls/test_demo.txt
   ```

2. In n8n, click **Execute** (play button)

3. Monitor execution in **Execution log**:
   - Green checkmarks = success
   - Red X = error (click for details)

4. Verify outputs:
   ```bash
   ls -la outputs/accounts/
   cat outputs/accounts/account_01/v1/account_memo.json
   ```

### Batch Test (All 5 Accounts)

1. Copy all demo files:
   ```bash
   cp dataset/demo_calls/demo_*.txt /your/local/dataset/
   ```

2. Place onboarding files:
   ```bash
   cp dataset/onboarding_calls/onboarding_*.txt /your/local/dataset/
   ```

3. Trigger workflow for each file (n8n watches the directory)

4. Monitor execution dashboard for all 5 accounts

5. Verify all outputs:
   ```bash
   find outputs/accounts -name "*.json" | wc -l
   # Should be 20 files (5 accounts × 2 versions × 2 types)
   ```

---

## Step 7: Deploy to Production (Optional)

### Cloud Deployment

For free n8n cloud hosting:

1. Create account at https://n8n.cloud (free tier available)
2. Export workflow from local n8n
3. Import to n8n cloud
4. Set up webhooks for file uploads
5. Configure cloud storage integration (AWS S3, Google Drive)

### Self-Hosted (Recommended for Privacy)

Deploy n8n on a server:

```bash
# VPS / Linux server with Docker
git clone <repo>
docker-compose up -d

# Access via domain (requires reverse proxy like Nginx)
# https://yourdomain.com/n8n/
```

### Scheduled Batch Processing

Configure cron trigger:

```
Node Type: Cron
Schedule: Every day at 9:00 AM
Timezone: America/New_York
```

This runs the pipeline automatically on a schedule.

---

## Monitoring & Maintenance

### Dashboard

- **Executions:** See all workflow runs with status
- **Logs:** Debug failed runs
- **Performance:** Check execution time and resource usage

### Alerts

Set up notifications:

```
Node Type: Send Slack Message
Trigger: On workflow error
Message: ⚠️ Pipeline failed: {{ $node["error"].message }}
```

Or use email, webhook, Discord, etc.

### Backup Workflow

1. Export workflow regularly:
   - **Menu** → **Download** → Save `workflow.json`

2. Backup n8n data:
   ```bash
   docker-compose exec n8n tar -czf /home/node/.n8n/backup.tar.gz .
   docker cp clara-n8n:/home/node/.n8n/backup.tar.gz ./
   ```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| n8n won't start | Check Docker: `docker ps`, restart: `docker-compose restart` |
| Nodes can't find scripts | Verify paths in Execute Command nodes; use absolute paths |
| File trigger not firing | Check file permissions, restart trigger node |
| Python errors in logs | Verify Python version (3.10+), test scripts manually first |
| Out of disk space | Clean `/tmp/` and old outputs, increase Docker volume size |
| Timezone mismatch | Set `GENERIC_TIMEZONE` in docker-compose.yml |

---

## Alternative: Run Pipeline Without n8n

If you prefer a simpler setup without n8n:

```bash
# Direct Python execution
python3 scripts/run_pipeline.py

# Or with cron (for automated scheduling)
0 9 * * * cd /path/to/clara-assignment && python3 scripts/run_pipeline.py
```

---

## Next Steps

1. ✓ Start n8n (Docker Compose)
2. ✓ Import workflow
3. ✓ Test with sample files
4. ✓ Add all 5 demo + 5 onboarding files
5. ✓ Monitor execution dashboard
6. ✓ Review outputs in `/outputs/` and `/changelog/`
7. ✓ (Optional) Deploy to cloud or VPS

---

## Support

- **n8n Docs:** https://docs.n8n.io/
- **n8n Community:** https://community.n8n.io/
- **This Project:** See [README.md](./README.md) and [SETUP_DEPLOYMENT.md](./SETUP_DEPLOYMENT.md)
