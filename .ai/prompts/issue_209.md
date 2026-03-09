---
Story
As a release operator,
I want a defined benchmark maintenance cadence with automated scheduling,
So that performance regressions are detected early with auditable evidence.

Context / Why
We have ORIN benchmark artifacts and regression thresholds, but no explicit cadence or schedule, which risks stale performance visibility and weak governance evidence.

Acceptance Criteria
- Given GitHub Actions scheduling, when the cadence triggers, then workflow `ORIN Backend Benchmark` runs on the self-hosted runner and uploads artifact `orin-backend-benchmark`.
- Given a regression beyond `deploy/orin/benchmark_thresholds.json`, when the workflow runs, then job `ORIN benchmark + threshold gate` fails with a clear threshold error in logs.
- Given `docs/runbook_orin_deploy.md`, when an operator follows the benchmark runbook, then it documents the cadence and how to fetch the benchmark artifacts.
- CI proof: `ORIN Backend Benchmark` workflow job `ORIN benchmark + threshold gate` and artifact `orin-backend-benchmark`.

Out of Scope
- Adding new benchmark scenarios or changing the benchmark metric definitions.

Notes
- Keep benchmark artifacts share-safe (no PHI/PII).
---
