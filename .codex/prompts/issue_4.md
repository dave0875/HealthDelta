# issue_4

Issue: https://github.com/dave0875/HealthDelta/issues/4

Prompt (verbatim)

```
Open a NEW GitHub issue (#4) using the story template.

Title:
Ingest bootstrap: Apple Health export.zip/unpacked -> deterministic staging + manifest

Story:
As a HealthDelta maintainer,
I want a deterministic ingest CLI that accepts an Apple Health export.zip or an unpacked export directory,
so that we can build identity resolution, de-identification, NDJSON, and DuckDB summaries incrementally with reliable, testable artifacts.

Acceptance Criteria:
- Provide a CLI entrypoint `healthdelta ingest --input <path> [--out data/staging]`.
- `--input` supports:
  - a path to `export.zip`, OR
  - a path to an unpacked export directory containing `export.xml` and clinical JSON(s).
- On each run it creates a run directory: `data/staging/<run_id>/` where run_id is deterministic or reproducible (document choice).
- It copies or references source files into the run directory, and writes:
  - `manifest.json` with:
    - run_id
    - input path (redacted if needed)
    - file list with sizes + sha256
    - counts: xml record count estimate + clinical json file count
    - timestamps
  - `layout.json` describing where export.xml and clinical assets are located in staging
- Determinism requirement: same input bytes => same file hashes in manifest; manifest fields that vary by time must be clearly separated or normalized.
- Unit tests:
  - zip vs unpacked path handling
  - manifest determinism for a fixed fixture
- Update docs minimally: add `docs/runbook_ingest.md` and reference it from AGENTS.md.
- Record `.codex/prompts/issue_4.md` (immutable) and session notes; TIME.csv entries required.

Constraints / rules:
- All repo mutations on GORF only.
- No scope creep into identity resolution, NDJSON schema, DuckDB modeling, or de-identification yet.
- Keep it a thin vertical slice with tests and CI green.

Proceed:
1) Create Issue #4
2) Implement per acceptance criteria
3) Ensure CI passes
4) Close Issue #4 with evidence
```

