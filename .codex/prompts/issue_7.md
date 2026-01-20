# issue_7

Issue: https://github.com/dave0875/HealthDelta/issues/7

Prompt (verbatim)

```
Open a NEW GitHub issue (#7) using the story template.

Title:
Pipeline orchestrator: one command to run ingest -> identity -> deid with deterministic outputs

Story:
As a HealthDelta user/maintainer,
I want a single pipeline command that orchestrates the existing steps (ingest, identity build, deid),
so I don’t need to remember internal CLI ordering and paths, and so runs can be reproduced from a single run report.

Context / Why:
We now have discrete steps:
- Issue #4: ingest staging -> data/staging/<run_id> (manifest.json + layout.json)
- Issue #5: identity build -> data/identity/people.json + aliases.json
- Issue #6: deid -> data/deid/<run_id> with mapping.json and de-identified copies (including CDA + FHIR JSON)
Users should not have to manually chain these steps or infer correct paths; orchestration must be part of the product.

Acceptance Criteria:
- Add a top-level orchestrator command:
  `healthdelta pipeline run --input <path> [--out <base_dir>] [--mode local|share] [--run-id <run_id>] [--skip-deid]`
- Input handling:
  - Accept either:
    1) a path to an unpacked Apple Health export directory, OR
    2) a path to export.zip (optional if already supported by ingest; if not supported, document and keep to directories only for this issue)
  - The pipeline must not upload or exfiltrate data; it operates purely on local filesystem.
- Orchestration behavior:
  - Stage 1: call existing ingest implementation to create data/staging/<run_id> (or <base_dir>/staging/<run_id> if --out provided)
  - Stage 2: call existing identity build using the staged run_id
  - Stage 3 (conditional):
    - If --mode share: run deid and ensure final “share-safe” output directory is created
    - If --mode local: do not run deid unless explicitly requested (e.g., no deid by default)
    - If --skip-deid: never run deid even in share mode (for debugging; document risk)
- Outputs:
  - Always emit a deterministic `run_report.json` under the run directory (choose a stable location and document it), containing:
    - run_id
    - start/end timestamps
    - input summary (redacted paths; include hashes/sizes where already available from manifest)
    - which stages executed (ingest/identity/deid) and their output directories
    - counts (files processed where available without parsing values)
    - tool versions (python version, healthdelta version)
  - The report MUST NOT include PII (no names, no DOB, no MRNs).
- Determinism + idempotency:
  - If the run directory already exists and the inputs match (based on manifest hashes/sizes), the pipeline should:
    - either skip stages safely OR re-run in a way that does not duplicate alias records (existing identity logic already claims stable alias_key)
  - Provide clear exit codes and human-readable summaries.
- Tests:
  - Synthetic-only fixtures (no real health data)
  - Add an integration-style test that runs the pipeline end-to-end on tiny synthetic inputs:
    - includes tiny export.xml + tiny export_cda.xml + 1–2 FHIR JSON resources
    - asserts directories are created and run_report.json is present
    - asserts share mode produces deid outputs and mapping.json without original synthetic names/DOB
- Docs:
  - Add `docs/runbook_pipeline.md` describing common invocations:
    - local mode for private use
    - share mode for generating de-identified artifacts
    - rerun behavior
  - Update AGENTS.md to require following runbook_pipeline.md for orchestration work.
- Engineering discipline:
  - All repo mutations on GORF only
  - Create `.codex/prompts/issue_7.md` (immutable); followups use issue_7_followup_X.md (X=1–9)
  - Update TIME.csv and add session/review artifacts
- Close Issue #7 only when CI is green.

Out of Scope:
- NDJSON schema/exporters and DuckDB summaries (next issues)
- Any CD/TestFlight/release automation
- Full PII scrub across all possible FHIR fields beyond what deid already covers
```

