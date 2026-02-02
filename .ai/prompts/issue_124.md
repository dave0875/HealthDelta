---
Story
As a user,
I want clinically-oriented risk flags with transparent evidence,
So that I can quickly identify records that need human follow-up.

Context / Why
Risk flags are highest priority in the super prompt. They must be information-only, auditable, and never framed as medical advice.

Acceptance Criteria
- Given canonical patient timelines, when risk-flag analysis runs, then outputs include deterministic flag categories and severities.
- Given each emitted flag, when output is rendered, then evidence links to source records and rationale text are included.
- Given safety constraints, when output is generated, then a clear non-medical-advice disclaimer is always present.
- Given validation tests, when CI runs, then fixtures verify deterministic flag output and evidence traceability.

Out of Scope
- Automated treatment recommendations.
- External clinician workflow integrations.

Notes
- Start with a constrained ruleset, then expand in follow-up issues.
---
