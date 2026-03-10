Issue: #217

Title: Stabilize ORIN DuckDB/report generation for iOS incremental exports

Source of truth
- GitHub issue #217

Scope
- Make the validated iPhone -> Mac -> ORIN transfer path produce working DuckDB and share-safe report artifacts for a copied iOS incremental export on ORIN.
- Focus on the failing ORIN-side analytics/runtime path after copied iOS export ingest has already succeeded.

Constraints
- Keep direct iPhone -> ORIN upload out of scope.
- Preserve share-safe report behavior.
- Prefer the smallest fix that restores reliable operator execution on ORIN and keeps CI proof aligned.

Acceptance focus
- A copied iOS incremental export on ORIN can be ingested and then converted into a usable DuckDB database without hanging.
- Report generation from that ORIN-side input succeeds and produces share-safe artifacts.
- `CI` / `linux-tests` continues to pass as proof for the stabilized code path.
- Operator documentation matches the working ORIN flow.
