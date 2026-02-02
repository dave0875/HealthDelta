---
Story
As a maintainer,
I want PHI-leakage and safety guardrail tests enforced in CI,
So that local inference outputs remain share-safe and auditable.

Context / Why
Planning and deployment are insufficient without automated checks for PHI leakage, disclaimer presence, and citation/traceability requirements.

Acceptance Criteria
- Given inference outputs/logs from synthetic fixtures, when CI checks run, then banned PHI patterns are rejected.
- Given summary/risk/trend/Q&A outputs, when validation runs, then required disclaimer and citation fields are enforced.
- Given failures, when CI reports results, then artifacts include machine-readable safety check logs.
- Given merge criteria, when guardrails fail, then PR status is blocking.

Out of Scope
- Clinical quality evaluation beyond safety/compliance guardrails.
- Human reviewer UI.

Notes
- This issue is a quality gate for Orin feature issues.
---
