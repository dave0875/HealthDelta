---
Story
As an operator,
I want a reproducible production deployment path for `orin.local`,
So that backend releases can be installed, verified, and rolled back safely.

Context / Why
The repo has CI/release workflows, but Orin-specific deployment proof and operational checks are not yet codified.

Acceptance Criteria
- Given a tagged release artifact, when deployment procedure is executed on Orin, then backend service starts and serves `/healthz` and `/version`.
- Given deployment validation, when smoke tests run, then risk/summary endpoints return expected shape against synthetic fixtures.
- Given rollback requirements, when deployment fails, then documented rollback returns previous known-good version.
- Given governance requirements, when deployment is declared ready, then CI/job/artifact evidence is referenced in runbook and issue closure notes.

Out of Scope
- Feature development for inference logic.
- Remote shell automation tooling beyond deployment runbook needs.

Notes
- Prefer deterministic scripts and system service definitions over manual steps.
---
