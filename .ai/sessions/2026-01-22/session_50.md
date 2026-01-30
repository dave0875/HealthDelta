# Session 50 — 2026-01-22

Issues worked
- #56 Release: fix tag builds to produce exact PEP 440 version (no .post/.dev)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Updated `Release` workflow to force tag builds to use the exact tag version via `SETUPTOOLS_SCM_PRETEND_VERSION`.

Local verification
- N/A (workflow-driven change)

CI evidence
- PR: https://github.com/dave0875/HealthDelta/pull/57
- CI run: https://github.com/dave0875/HealthDelta/actions/runs/21250796827

Release proof
- Green: https://github.com/dave0875/HealthDelta/actions/runs/21250858987 (`v0.0.2`)
