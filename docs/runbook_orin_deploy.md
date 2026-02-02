# Runbook: ORIN backend deployment (docker compose)

This runbook covers the ORIN-side prerequisites and operational commands for backend deployments.

## Deployment workflow
- Workflow: `.github/workflows/deploy_backend_orin.yml`
- Trigger: tag `vX.Y.Z` (or manual dispatch with `tag=vX.Y.Z`)
- Runner: ORIN self-hosted GitHub Actions runner (LAN-local)
- Deploy dir: `/opt/healthdelta`
- Persistent data dir: `/opt/healthdelta/data` (bind-mounted into container `/app/data`)

## Benchmark workflow (Issue #162)
- Workflow: `.github/workflows/orin_backend_benchmark.yml`
- Trigger: manual dispatch (`workflow_dispatch`)
- Runner: ORIN self-hosted GitHub Actions runner (`self-hosted`, `linux`, `orin`)
- Inputs:
  - `base_url` (default `http://127.0.0.1:8080`)
  - `summary_input_path` (default `/app/deploy/fixtures/profile_export`)
  - `pipeline_input_path` (default `tests/fixtures/profile_export`)
  - `iterations` and `pipeline_iterations`
- Output artifact: `orin-backend-benchmark`
  - `benchmark_results.json` (machine-readable metrics)
  - `benchmark_report.md` (operator-readable summary)
- Regression policy thresholds are defined in `deploy/orin/benchmark_thresholds.json`.
- CI fails with explicit metric diagnostics when observed values exceed thresholds.

## Planning artifact linkage
- Model/runtime planning matrix for ORIN MMF workloads: `docs/orin_model_runtime_matrix.md` (Issue #122).
- This matrix is the source for summary/risk/trend/Q&A runtime selection and latency/memory envelopes.

## Runner diagnostics proof workflow
- Workflow: `.github/workflows/orin_runner_diagnostics.yml`
- Trigger: manual dispatch
- Purpose: prove runner scheduling + capture host environment evidence without deploying.
- Expected artifact: `orin-runner-env` containing `env.txt` (uname/arch/docker/docker compose versions).

## ORIN prerequisites
1) GitHub Actions self-hosted runner installed on ORIN
   - Labels must include: `self-hosted`, `linux`, `orin` (matches workflow `runs-on`)
2) Docker installed and runner user can run Docker
   - Runner user must be able to execute `docker` and `docker compose` without interactive prompts.
3) Tools required for verification
   - `curl`
   - `python3`
4) Deploy directory permissions
   - Required one-time bootstrap (no sudo during workflow execution):
     - `sudo mkdir -p /opt/healthdelta`
     - `sudo mkdir -p /opt/healthdelta/data`
     - `sudo chown -R <runner-user>:<runner-user> /opt/healthdelta`
   - The deploy workflow does not use sudo; it fails fast if the directory is missing/not writable.
   - The deploy workflow copies `deploy/orin/compose.yaml`, writes `/opt/healthdelta/.env`, and verifies `/opt/healthdelta/data` is writable.

## What gets deployed
- Compose template: `deploy/orin/compose.yaml`
- Pinned tag file: `/opt/healthdelta/.env` with `HEALTHDELTA_BACKEND_IMAGE_TAG=vX.Y.Z`
- Bind mount: `/opt/healthdelta/data:/app/data`
- Service listens on `http://127.0.0.1:8080` (port mapping `8080:8080`)

## Vertical slice endpoint (Issue #123)
- Endpoint: `POST /summary`
- Purpose: run a minimal ingest -> identity -> de-id -> NDJSON vertical slice and return a share-safe summary response.
- Required request fields:
  - `input_path`: local path to a synthetic/unpacked export fixture
- Optional request fields:
  - `work_dir`: scratch output root (default `data/backend_slice`)
  - `citation_limit`: max response citations (default 12, capped at 50)
- Response includes:
  - deterministic stream-count summary text
  - citation list (`stream`, `record_key`, `source_file`, `event_time`, `line`)
  - deterministic risk flags (`flag_id`, `category`, `severity`, `rationale`, `evidence`)
  - trend analysis (`metric`, `window_days`, `direction`, `confidence`, `delta`) with explicit insufficiency reporting
  - mandatory disclaimer string stating flags are not medical advice
  - PHI token guard check result (`phi_tokens_checked`, `phi_token_hits`)

## Verification (“150%” backend checks)
The deploy workflow verifies:
- GHCR tag manifest is available before compose pull (bounded wait loop).
- Correct image tag is running (container image contains `:vX.Y.Z`)
- `GET /healthz` returns 200
- `GET /version` returns `version=X.Y.Z` and `git_sha=<sha>`
- Data-plane correctness:
  - `/app/data` is a real bind mount
  - mount source equals `/opt/healthdelta/data`
  - sentinel write/read works inside container and on host
  - sentinel persists across service restart
- `POST /summary` succeeds against synthetic fixture path and includes citations + risk/trend payload shape
- `POST /qa` succeeds against synthetic fixture path and includes citations + disclaimer
- Synthetic fixture path used in-container: `/app/deploy/fixtures/profile_export`
- Recent logs do not contain obvious fatal indicators (bounded tail scan)
- Workflow uploads artifact `orin-deploy-proof` containing:
  - `deploy_verify.log`
  - `summary_response.json`
  - `qa_response.json`
  - `metadata.txt` (tag/version/sha/run URL)
- CI Linux job also uploads backend slice evidence artifacts:
  - `artifacts/linux/backend_slice/smoke.log`
  - `artifacts/linux/backend_slice/summary_response.json`

Benchmark verification adds:
- p50/p95 latency metrics for `POST /summary` and `POST /qa`
- p50/p95 runtime metrics for `healthdelta pipeline run` on synthetic fixture input
- threshold enforcement messages in the form:
  - `metric=<name> threshold<= <value> observed= <value>`
  - This enables deterministic pass/fail debugging without reading raw logs.

## Grounded Q&A endpoint (Issue #126)
- Endpoint: `POST /qa`
- Required request fields:
  - `input_path`: local path to synthetic/unpacked export fixture
  - `question`: question text
- Response includes:
  - `qa.answer` text
  - `qa.citations` references to local records
  - `qa.abstained` flag for low-evidence queries
  - mandatory `qa.disclaimer` (not medical advice)

## Rollback
Use deterministic rollback helper:

```bash
ROLLBACK_TAG=v0.0.1 ROLLBACK_SHA=<git_sha_for_tag> \
  DEPLOY_DIR=/opt/healthdelta BASE_URL=http://127.0.0.1:8080 \
  bash scripts/cd/orin_rollback_backend.sh
```

This script:
- rewrites `/opt/healthdelta/.env` to the rollback tag
- redeploys compose service
- re-runs the same verify contract (`/healthz`, `/version`, data-plane checks, `/summary`, `/qa`)

## Credentials / secrets
- The workflow uses `GITHUB_TOKEN` for `docker login ghcr.io` with `packages: read` permission.
- If GHCR pulls fail on ORIN, use a fine-grained PAT with `read:packages` via a new secret and update the workflow accordingly (do not commit tokens).

## Local reproduction (on ORIN runner host)
Run benchmark + threshold check without GitHub Actions:

```bash
python3 scripts/cd/orin_benchmark_backend.py \
  --base-url http://127.0.0.1:8080 \
  --summary-input-path /app/deploy/fixtures/profile_export \
  --pipeline-input-path tests/fixtures/profile_export \
  --iterations 5 \
  --pipeline-iterations 3 \
  --out-json artifacts/orin-benchmark/benchmark_results.json \
  --out-md artifacts/orin-benchmark/benchmark_report.md

python3 scripts/cd/check_benchmark_thresholds.py \
  --results artifacts/orin-benchmark/benchmark_results.json \
  --thresholds deploy/orin/benchmark_thresholds.json
```

Validate mount and sentinel manually:

```bash
cid="$(docker compose -f /opt/healthdelta/compose.yaml --env-file /opt/healthdelta/.env ps -q backend)"
docker inspect "$cid" --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Source}} -> {{.Destination}}{{end}}{{end}}'
cat /opt/healthdelta/data/.healthdelta_sentinel
```
