# ADR 3: Doctor’s Note as reusable component with operator integration

Status: Accepted

## Context

- Issue #12 introduced the one-command operator workflow (`healthdelta run all`) that orchestrates the end-to-end pipeline and produces share-safe artifacts.
- During execution of Issue #12, a concise, share-safe “Doctor’s Note” output was identified as a reusable capability for operators who need a one-screen copy/paste summary.
- Per governance, this capability was implemented as a separate issue (Issue #13) rather than retroactively changing Issue #12 scope.

Cross-references:
- Issue #12: https://github.com/dave0875/HealthDelta/issues/12
- Issue #13: https://github.com/dave0875/HealthDelta/issues/13
- Issue #14: https://github.com/dave0875/HealthDelta/issues/14

## Decision

- Implement Doctor’s Note as a standalone command (`healthdelta note build`) in Issue #13.
- Integrate Doctor’s Note generation into the operator command in Issue #14 so the operator path produces Doctor’s Note automatically as part of the one-command experience.

## Consequences

- Operators get a one-command experience that produces an immediately share-safe, one-screen summary.
- Doctor’s Note remains reusable as an independent building block for future integrations (UI, API, exports).
- Governance and history remain unambiguous:
  - Issue #12 scope is not retroactively mutated.
  - The additive requirement is captured as Issue #13 (feature) and Issue #14 (integration + explicit architectural record).

