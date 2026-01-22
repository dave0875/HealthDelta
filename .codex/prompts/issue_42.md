Issue: https://github.com/dave0875/HealthDelta/issues/42

Scope / intent (immutable)
- Document (via an ADR) how the two current ingestion paths (Apple Health export.zip / unpacked export directory vs iOS incremental exports) converge on shared invariants, so future schema/pipeline work remains consistent and auditable.

Acceptance criteria (restated)
- Add an ADR under `docs/adr/` describing:
  - the two ingestion paths
  - shared invariants (no PII, deterministic outputs, person-keying)
  - how NDJSON schema aligns across paths (current and planned)
- Reference the ADR from `AGENTS.md`.
- Record audit artifacts (prompt/session/review/TIME.csv) and close with green CI.

Plan
1) Write `docs/adr/ADR_4_ingestion_paths_convergence.md` describing:
   - Path A: Apple export.zip / export directory → staging → identity → (optional) deid → NDJSON → DuckDB → reports
   - Path B: iOS incremental export → iOS NDJSON+manifest → (optional) deterministic staging ingest → DuckDB → reports
   - Convergence invariants: deterministic, share-safe, no PII, stable IDs/keys, artifact-based verification
   - Alignment: shared core fields (`canonical_person_id`, `event_time`, `source`, `run_id`, `source_file`) and bounded divergence (extra iOS fields)
2) Update `AGENTS.md` to reference the ADR.
3) Run local tests; push; verify CI green; comment + close.

Constraints
- Documentation must be share-safe (no PHI/PII examples, no real export paths).
