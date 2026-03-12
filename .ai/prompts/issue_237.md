# Issue #237 Prompt

Issue: #237
Title: Bootstrap-aware ORIN accumulation for iPhone uploads

Immutable execution prompt recorded at start of work.

Scope
- Make ORIN cumulative iPhone finalize inherit a manually installed Apple bootstrap dataset when that dataset is already the live `current`.
- Preserve duplicate-safe row merging when a later iPhone delta overlaps the bootstrap baseline.
- Keep `/patients/current` and `/insights/current` grounded in the merged baseline+delta dataset instead of discarding the bootstrap.

Goals
- Detect when the previous `current` dataset is a non-iPhone bootstrap but still has canonical observations available in existing analysis artifacts.
- Materialize a cumulative iPhone-compatible current dataset from that bootstrap baseline plus the new delta upload.
- Add regression coverage proving the bootstrap dataset remains in scope after the first later iPhone upload.

Constraints
- No secrets in `.ai/`.
- Use TDD for the new bootstrap-aware accumulation logic.
- Keep `main` releasable and verify CI + Release before closure.
