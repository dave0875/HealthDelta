Issue #243: Preserve strong labels for numeric wellness data from Apple export

URL: https://github.com/dave0875/HealthDelta/issues/243

Story
As a HealthDelta user,
I want numeric wellness data from Apple exports to preserve strong measurement labels,
So that fitness and wellness trends can be interpreted by actual signal name instead of anonymous units or unknown buckets.

Context / Why
The current ORIN baseline shows a large unresolved wellness bucket where numeric Apple-export rows are mostly unlabeled. Unit mixes strongly suggest heart rate, steps, oxygen saturation, energy, distance, and audio exposure are present, but the extraction path is not preserving those signal labels strongly enough for trustworthy summaries or trends.

Acceptance Criteria
- Given an Apple export with numeric wellness records, when it is processed into canonical observations, then the resulting rows preserve strong signal labels such as HealthKit type or equivalent deterministic display text instead of collapsing into unknown buckets.
- Given the reprocessed baseline, when querying recent wellness activity, then the dominant wellness signals can be named directly rather than inferred only from units.
- Given the fix, when temporary rebuild artifacts are no longer needed, then scratch files are pruned and disk usage remains bounded.
- CI and Release remain green.

Out of Scope
- Redesigning the iPhone UI.
- Adding new data sources beyond the existing Apple export.
- Inventing wellness labels that are not grounded in the source export.

Notes
- Prefer fixes at extraction or canonicalization layers over downstream heuristics.
- Reuse the original Apple export baseline for validation.
