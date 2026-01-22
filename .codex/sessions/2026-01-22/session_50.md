# Session 50 — 2026-01-22

Issues worked
- #56 Release: fix tag builds to produce exact PEP 440 version (no .post/.dev)

Execution environment
- Repository mutations executed on Ubuntu host: `GORF`

Work summary
- Updated `Release` workflow to force tag builds to use the exact tag version via `SETUPTOOLS_SCM_PRETEND_VERSION`.

Local verification
- N/A (workflow-driven change)
