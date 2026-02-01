---
Story
As an operator,
I want an issue-backed, phased plan for production deployment on `orin.local` (Jetson Orin Nano Super),
So that we can ship a local-only backend analytics target with auditable, incremental MMFs.

Context / Why
A super prompt exists for Jetson-focused local medical analytics planning, but the repo needs this translated into HealthDelta issue backlog, deployment milestones, and runbook-ready acceptance criteria. Without this planning phase, deployment work will be ad hoc and difficult to validate.

Acceptance Criteria
- Given the Jetson super prompt and current repository state, when planning is completed, then a prioritized MMF backlog is published as GitHub issues using the required template.
- Given the new MMF backlog, when docs are updated, then `docs/plan.md` includes an explicit "Orin production deployment" phase with ordered issue links.
- Given backend deployment scope, when runbook planning docs are updated, then `docs/runbook_cd.md` includes Orin-specific deployment-proof criteria (what CI/job/artifact proves readiness).
- Given governance requirements, when this planning issue is executed, then `.ai/prompts/issue_N.md`, `.ai/sessions/`, and `.ai/time/time.csv` are updated for the active issue.

Out of Scope
- Implementing Orin deployment code, infra, or runtime tuning.
- Operating remote shell on `orin.local`.

Notes
- Planning must preserve local-only inference and share-safe output constraints.
- Backlog should prioritize risk flags and summaries before trends and Q&A.
---
