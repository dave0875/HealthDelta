# Clinical Records Fixture Pack v1

Synthetic FHIR resource files for deterministic NDJSON mapping tests.

Constraints:
- all resources are synthetic and share-safe
- no real patient names, identifiers, or absolute host paths
- attachment payloads are synthetic and small enough for CI use

Included resources:
- `patient.json`
- `observation.json`
- `document_reference.json`
- `binary.json`
- `provenance.json`

These fixtures are intended for canonical mapping tests only and must not be replaced with real export data.
