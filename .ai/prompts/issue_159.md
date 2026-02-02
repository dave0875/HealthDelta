# Issue #159 Prompt (Immutable)

Implement iOS UI for sync status and health insights.

Scope:
- Replace placeholder iOS screen with a Nielsen-heuristics-oriented dashboard.
- Show sync visibility at launch: last sync time, last delta window, exported rows/bytes, and anchor status.
- Add sync details view with deterministic run metadata (run id, files, counts, anchors) without PHI text.
- Add insights section that surfaces share-safe artifacts (Doctor's Note and summary) with disclaimer and freshness context.
- Handle first-run empty state with explicit next steps.
- Add iOS unit tests for deterministic formatting/state mapping for sync status and insight cards.

Do not add cloud/account features or clinical diagnosis functionality.
