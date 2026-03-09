---
Story
As a mapping developer,
I want a share-safe clinical records fixture pack,
So that mapping tests are deterministic and CI-safe.

Context / Why
Clinical records mapping work needs synthetic fixtures to avoid PHI while still exercising real-world structures.

Acceptance Criteria
- Given clinical records mapping tests, when fixtures are added, then a synthetic fixture pack exists under `tests/fixtures/clinical_records_v1` with a README describing sources and share-safe constraints.
- Given the fixtures, when mapping tests run, then at least one mapping test uses the new fixtures for coverage.
- Given the updates, when CI runs, then workflow `CI` job `Linux (non-iOS tests)` passes.

Out of Scope
- Implementing new mapping logic beyond test fixtures.
- Using any real patient data.

Notes
Keep all fixtures synthetic and avoid absolute paths or PHI.
---
