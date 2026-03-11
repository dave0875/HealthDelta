Issue: #229

Title: Make ORIN insight window and patient configurable from the iPhone app

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/229

Prompt
- Add first-class iPhone controls for the ORIN insight evaluation window and target patient.
- Keep the UI simple for this slice: a small fixed window selector plus an optional canonical person ID field is sufficient.
- Extend `GET /insights/current` so ORIN can accept those filters and compute cards from only the matching person/window instead of the implicit full dataset.
- Preserve current behavior when no filters are supplied.
- Return a deterministic no-insights-yet response when the selected filters match no rows.
- Add focused backend and iOS tests and update the operator documentation for the new controls.
