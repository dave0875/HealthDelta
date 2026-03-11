# Session 16

- Date: 2026-03-11
- Issue: #229
- Goal: Make ORIN insights configurable from the iPhone app by patient and evaluation window.

Actions
- Inspected the current iPhone insights client and confirmed it always calls `GET /insights/current` with no query parameters.
- Inspected the ORIN backend and confirmed the current endpoint always computes cards for the implicit current dataset with no person or time-window filtering.
- Scoped the implementation to a small iPhone UI control set plus backend query-parameter filtering that preserves current behavior when no filters are provided.
