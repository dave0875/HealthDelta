---
Story
As an operator,
I want DiagnosticReport resources exported and linked to Observation when possible,
So that lab panels and results are tied to reports.

Context / Why
Epic/MyChart results often arrive as DiagnosticReport + Observation.

Acceptance Criteria
- DiagnosticReport emits NDJSON rows with event_time from effective[x]/issued.
- If result references Observations in the same export, include a deterministic link field.
- Tests cover linkage and fallback when references are missing.

Out of Scope
- Full code system normalization.
---
