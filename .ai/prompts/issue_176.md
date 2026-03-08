---
Story
As a maintainer,
I want a governance and runbook audit,
So that contributors follow current, consistent procedures.

Context / Why
Runbooks and governance rules evolve quickly. Without periodic audits, documentation can drift, leading to mistakes and compliance gaps.

Acceptance Criteria
- Given the current runbooks, when the audit is complete, then outdated or missing references are updated and documented.
- Given governance rules in AGENTS.md and `.ai/`, when the audit is complete, then enforcement points and required artifacts are explicitly confirmed in documentation.
- Given this change, when `ci.yml` job `linux-tests` runs, then it passes.

Out of Scope
- Implementing new product features unrelated to governance or documentation.

Notes
- Deployment proof not required unless deployable artifacts are changed.
---
