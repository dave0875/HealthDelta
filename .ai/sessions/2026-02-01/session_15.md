# Session 15 - 2026-02-01

Issue: #132

Goal
- Add a safe ORIN diagnostics workflow that proves runner scheduling and uploads environment evidence.

Notes
- Added `.github/workflows/orin_runner_diagnostics.yml` with `runs-on: [self-hosted, linux, orin]`.
- Captures `uname -a`, `arch`, `docker --version`, and `docker compose version`.
- Uploads deterministic artifact `orin-runner-env` with `artifacts/orin/env.txt`.
- Updated `docs/runbook_orin_deploy.md` with diagnostics workflow usage.

Local verification
- YAML lint/parse by GitHub Actions on PR
