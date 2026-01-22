# Issue #22 — Profile-to-pipeline UX recommendations (immutable prompt)

Issue: https://github.com/dave0875/HealthDelta/issues/22

Host constraint (authoritative execution rule)
- All repository mutations occur ONLY on Ubuntu host `GORF`.
- macOS runner is used ONLY via GitHub Actions for Xcode work; no repo mutation on macOS.

## Acceptance criteria (restated)

- `profile.md` includes a deterministic “Next Steps” section with recommendations based on detected files.
- Recommendations remain share-safe (no paths outside export root; use placeholders).
- Tests assert the section exists and is deterministic.

## Plan

1) Update `healthdelta/profile.py` to emit a `## Next Steps` section with deterministic command suggestions:
   - prefer `healthdelta run all` as the operator entrypoint
   - include `healthdelta pipeline run` variants
   - add conditional notes when CDA/FHIR clinical content is detected (prefer `--mode share` before sharing outputs)
2) Update `tests/test_profile.py` to assert the section and command strings exist for both fixture layouts.
3) Closeout: session log, review notes, TIME.csv; push; verify CI green; comment + close Issue #22.

