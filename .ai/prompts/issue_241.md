Issue: #241
Title: Make doctor's note prompt produce clinically useful summaries instead of row-count filler

Objective
- Replace the current key-value-heavy doctor's note output with a share-safe summary that foregrounds health issues, trends, and meaningful findings.
- Preserve deterministic machine-readable facts needed by downstream ORIN insight generation.

Acceptance anchors
- The doctor's note leads with clinically meaningful summary text instead of observation-row-count filler.
- Limited datasets clearly explain scope and limitations without letting operational counts dominate the note.
- Automated tests verify the revised note-building path.
- CI and Release remain green.
