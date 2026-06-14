Issue: #260
Title: Repair and ingest malformed large export_cda.xml without excluding CDA

Objective
- Add a streaming-safe CDA repair path that preserves CDA-derived signal from large Apple Health exports without requiring operators to exclude `export_cda.xml`.
- Distinguish recoverable XML structure defects from obvious truncation, and fail clearly on unrecoverable truncated inputs.

Acceptance anchors
- A recoverably malformed `export_cda.xml` is repaired into a derived working copy and then processed successfully by profile/pipeline/operator flows.
- CDA-derived rows and coverage artifacts still appear after repair.
- Obvious truncation is rejected with a clear error instructing resubmission and naming `dave0875@gmail.com`.
- The repair path is streaming-safe and does not require loading the full CDA file into memory.
