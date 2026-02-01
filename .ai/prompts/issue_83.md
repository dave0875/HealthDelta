---
Story
As an operator,
I want DuckDB tables and reports to cover new FHIR resource types,
So that hospital records show up in Doctor’s Note and summary artifacts.

Context / Why
Exported records must surface in reporting outputs to be useful.

Acceptance Criteria
- DuckDB builds tables for new resource types or extends existing ones.
- Report outputs include counts/time ranges for each new type.
- Tests validate report contents.

Out of Scope
- Visualization UI.
---
