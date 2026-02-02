# Runbook: Continuous deployment / artifact publication

This runbook defines how HealthDelta produces share-safe build artifacts and what evidence constitutes “deployment proof”.

## Workflows

### CI (tests)
- Workflow: `.github/workflows/ci.yml`
- Proof:
  - Linux job passes (non-iOS tests).
  - Linux uploads deterministic evidence artifacts:
    - `linux-unittest` (`python_version.txt`, `unittest.log`)
    - `ndjson_validate.log` smoke validation output
    - `safety_report.json` + `safety.log` guardrail validation outputs
    - `policy_report.json` governance check outcomes (machine-readable)
  - macOS job passes and uploads `ios-xcresult`.
- Governance hardening behavior:
  - Governance checks are rewrite-tolerant and never crash on missing commit ranges.
  - Issue-reference gate is enforced by `scripts/check_issue_footer.py` and `scripts/check_pr_issue.py`.
  - Tests/build execution still runs when policy checks fail.
  - Governance failures are reported as explicit `policy failure` outcomes (not infra failures).

### Release (artifact publication)
- Workflow: `.github/workflows/release.yml`
- On every push to `main`:
  - Publishes `cli-dist` as a GitHub Actions artifact containing `dist/*` (Python wheel + sdist).
- On tags `vX.Y.Z` (and manual dispatch):
  - Creates/updates a GitHub Release and attaches the CLI `dist/*` artifacts.
  - Publishes backend image `ghcr.io/<owner>/healthdelta-backend:vX.Y.Z` and `:latest` as a multi-arch manifest (`linux/amd64`, `linux/arm64`).

## Operator guidance (share-safety)
- Never upload real Apple Health exports (or staged copies) to GitHub Actions artifacts or Releases.
- Only share-safe derived artifacts may be published (code builds, logs, synthetic test fixtures, CI reports).

## How to cut a CLI release
1) Decide the version and ensure `main` is ready to tag (must be tracked by an issue).
2) Create an annotated tag `vX.Y.Z` on `main`.
3) Push the tag to GitHub.
4) Confirm the `Release` workflow run is green and the GitHub Release has the expected assets attached.

Note: CLI packaging version is tag-derived; do not manually edit a fixed `version = ...` field in `pyproject.toml`.

## iOS distribution (current state)
- TestFlight / App Store distribution is not configured by default.
- Current authoritative proof for iOS is the macOS self-hosted CI runner (`ios-xcresult` artifact).
- Planned: distribution builds will set `MARKETING_VERSION` from the git tag and `CURRENT_PROJECT_VERSION` from the CI run number (helper: `scripts/cd/derive_ios_versions.py`).

## Backend service (current state)
- Minimal backend HTTP service exists for CD verification: `healthdelta serve` / `python -m healthdelta.backend_server`
- Endpoints:
  - `GET /healthz` → `{"ok": true}`
  - `GET /version` → includes `version` + `git_sha` (share-safe)
- Local dev (Docker):
  - Build: `docker build -t healthdelta-backend:dev .`
  - Run: `docker run --rm -p 8080:8080 healthdelta-backend:dev`
  - Verify: `curl -fsS http://127.0.0.1:8080/healthz` and `curl -fsS http://127.0.0.1:8080/version`
- Local dev (Compose): `docker compose -f compose.backend.dev.yaml up --build`
- Version injection for containers:
  - Build args: `HEALTHDELTA_VERSION`, `HEALTHDELTA_GIT_SHA`
- Runtime env vars: `HEALTHDELTA_VERSION`, `HEALTHDELTA_GIT_SHA`

## Orin production target (planning baseline)

Target host: `orin.local` (Jetson Orin Nano Super, local-only analytics).

Deployment proof for Orin-target issues must include:
- CI workflow/job evidence for build + tests tied to the issue.
- Artifact evidence for deployment package contents and version metadata.
- Smoke verification evidence from target-compatible run steps (`/healthz`, `/version`, `/summary`, `/qa`).
- Rollback procedure evidence that restores a known-good version deterministically.

For ORIN deploy proof artifacts, include:
- `deploy_verify.log`
- `summary_response.json`
- `qa_response.json`
- `metadata.txt`

Planning/sequence is tracked by:
- `docs/plan.md` Orin phase issues: #120-#128.

## References
- Production targets ADR: `docs/adr/ADR_5_continuous_deployment_targets.md`
