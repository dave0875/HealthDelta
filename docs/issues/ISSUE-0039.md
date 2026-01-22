# ISSUE-0039: Reports: include iOS incremental export coverage in summaries

GitHub: https://github.com/dave0875/HealthDelta/issues/39

## Objective
Ensure reports surface iOS-exported data distinctly so operators can validate coverage/timelines from incremental exports.

## Context / Why
iOS incremental exports are ingested into DuckDB via subset mapping. Reports currently group by `source`, but iOS rows should be visible as a distinct source category for operator validation.

## Acceptance Criteria
- Given a DB containing iOS-ingested rows, when running `healthdelta report build`, then `coverage_by_source.csv` includes `source=ios` rows where present.
- Outputs remain deterministic (stable ordering/bytes for the same DB).
- Synthetic-only tests cover the behavior.

## Non-Goals
- Advanced analytics.

## Risks
- Risk: Derived “ios” grouping could misclassify non-iOS rows if `source_file` matches `ndjson/%`.
  - Mitigation: Use a narrow heuristic (`source_file LIKE 'ndjson/%'`) consistent with the iOS loader mapping.

## Test Plan
- Local: `python3 -m unittest discover -s tests -p 'test_*.py'`
- CI: green run link + macOS `ios-xcresult` artifact

## Rollback Plan
- Revert commit(s); reports revert to raw `source` grouping only.

