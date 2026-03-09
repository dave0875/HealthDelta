# Runbook: Canonical NDJSON Export (`healthdelta export ndjson`)

This runbook defines how HealthDelta exports canonical, share-safe NDJSON streams from pipeline outputs.

## Command

```bash
healthdelta export ndjson --input <pipeline_run_dir> --out <dir> [--mode local|share]
```

Inputs:
- `--mode local`: `--input` must be a staging run directory like `data/staging/<run_id>`.
- `--mode share`: `--input` should be a de-id run directory like `data/deid/<run_id>` (share-safe).

The exporter never uploads data; it reads local files only.

## Output files

Written under `--out`:
- `observations.ndjson` (always)
- `documents.ndjson` (always)
- `binaries.ndjson` (only if FHIR Binary resources are present)
- `medications.ndjson` (only if FHIR medication resources are present)
- `conditions.ndjson` (only if Condition records are present)
- `goals.ndjson` (only if FHIR Goal resources are present)
- `careplans.ndjson` (only if FHIR CarePlan resources are present)
- `service_requests.ndjson` (only if FHIR ServiceRequest resources are present)
- `coverages.ndjson` (only if FHIR Coverage resources are present)
- `organizations.ndjson` (only if FHIR Organization resources are present)
- `practitioners.ndjson` (only if FHIR Practitioner resources are present)
- `locations.ndjson` (only if FHIR Location resources are present)
- `imaging_studies.ndjson` (only if FHIR ImagingStudy resources are present)
- `specimens.ndjson` (only if FHIR Specimen resources are present)
- `devices.ndjson` (only if FHIR Device resources are present)
- `provenance.ndjson` (only if FHIR Provenance resources are present)

NDJSON is one JSON object per line (newline-terminated).

## Common schema (all streams)

Every emitted line includes:
- `schema_version`: schema version integer.
- `record_key`: stable, deterministic record key (sha256-based) used for dedupe and downstream loading.
- `canonical_person_id`: canonical person key (UUID string) when resolvable; otherwise the literal `"unresolved"`.
- `source`: `"healthkit"` | `"fhir"` | `"cda"`.
- `source_file`: relative, redacted path within the run directory (never an absolute host path).
- `event_time`: best-available timestamp as an ISO-8601 string (UTC `...Z`) when parseable; otherwise `null` or an unparsed string.
- `run_id`: the pipeline/staging run id.

Fields that MUST NOT appear in NDJSON:
- names
- dates of birth
- free-text patient identifiers (MRNs, raw patient IDs, etc.)

## Source handling

### HealthKit XML (`export.xml`)
- Stream-parses `<Record>` elements and emits them as observation rows.
- `event_time` selection: prefer `startDate`, otherwise `endDate`.

### FHIR JSON (`clinical-records/*.json`)
- Treats each file as a single resource (not Bundles).
- Exports only:
  - `Observation` → `observations.ndjson`
  - `DocumentReference` → `documents.ndjson`
  - `Binary` → `binaries.ndjson`
  - `MedicationRequest` → `medications.ndjson`
  - `MedicationStatement` → `medications.ndjson`
  - `MedicationDispense` → `medications.ndjson`
  - `Condition` → `conditions.ndjson`
  - `AllergyIntolerance` → `conditions.ndjson`
  - `Immunization` → `observations.ndjson`
  - `Procedure` → `procedures.ndjson`
  - `Goal` → `goals.ndjson`
  - `CarePlan` → `careplans.ndjson`
  - `ServiceRequest` → `service_requests.ndjson`
  - `Coverage` → `coverages.ndjson`
  - `Organization` → `organizations.ndjson`
  - `Practitioner` → `practitioners.ndjson`
  - `Location` → `locations.ndjson`
  - `ImagingStudy` → `imaging_studies.ndjson`
  - `Specimen` → `specimens.ndjson`
  - `Device` → `devices.ndjson`
  - `Provenance` → `provenance.ndjson`
- `Patient` resources are used for identity resolution only and are not exported.
- `event_time` selection for medication rows:
  - `MedicationRequest`: `authoredOn`
  - `MedicationStatement`: `effectiveDateTime`, else `effectivePeriod.start`, else `effectivePeriod.end`
  - `MedicationDispense`: `whenHandedOver`, else `whenPrepared`
  - `Condition`: `recordedDate`, else `onsetDateTime`
  - `AllergyIntolerance`: `onsetDateTime`, else `recordedDate`
  - `Immunization`: `occurrenceDateTime`
  - `Procedure`: `performedDateTime`, else `performedPeriod.start`, else `performedPeriod.end`
  - `Goal`: `startDate`, else first `target.dueDate`
  - `CarePlan`: `period.start`, else `period.end`, else `created`
  - `ServiceRequest`: `authoredOn`
  - `Coverage`: `period.start`, else `period.end`
  - `ImagingStudy`: `started`
  - `Specimen`: `collection.collectedDateTime`, else `collection.collectedPeriod.start`, else `collection.collectedPeriod.end`, else `receivedTime`
  - `Provenance`: `recorded`

### Observation fields

Canonical `Observation` rows include, when present:
- `record_id`
- `record_type`
- `observation_id`
- `subject_reference`
- `encounter_id`
- `effective_start`
- `effective_end`
- `code_system`
- `code`
- `display`
- `value`
- `unit`
- `components`

Observation `components` are emitted as a stable, share-safe list of structured component summaries ordered deterministically by code and value fields.

### Condition fields

Canonical `Condition` rows include, when present:
- `code_system`
- `code`
- `display`
- `clinical_status`
- `verification_status`
- `onset_time`

Missing Condition fields are emitted with deterministic null/empty behavior in the row JSON and counted in a share-safe stderr warning summary:
- `warnings.condition_missing.code=<n>`
- `warnings.condition_missing.clinical_status=<n>`
- `warnings.condition_missing.verification_status=<n>`

### Medication and Allergy fields

Canonical medication rows include, when present:
- `code_system`
- `code`
- `display`
- `status`

Canonical `AllergyIntolerance` rows include, when present:
- `code_system`
- `code`
- `display`
- `status`

Missing medication/allergy code or status fields are counted in the share-safe stderr warning summary:
- `warnings.medication_missing.code=<n>`
- `warnings.medication_missing.status=<n>`
- `warnings.allergy_missing.code=<n>`
- `warnings.allergy_missing.status=<n>`

### Immunization and Procedure fields

Canonical `Immunization` rows include, when present:
- `code_system`
- `code`
- `display`
- `status`

Canonical `Procedure` rows include, when present:
- `code_system`
- `code`
- `display`
- `status`

Missing immunization/procedure code or status fields are counted in the share-safe stderr warning summary:
- `warnings.immunization_missing.code=<n>`
- `warnings.immunization_missing.status=<n>`
- `warnings.procedure_missing.code=<n>`
- `warnings.procedure_missing.status=<n>`

### Encounter fields

Canonical `Encounter` rows include, when present:
- `record_id`
- `record_type`
- `encounter_id`
- `subject_reference`
- `period_start`
- `period_end`
- `status`

### DiagnosticReport fields

Canonical `DiagnosticReport` rows include, when present:
- `record_id`
- `record_type`
- `diagnostic_report_id`
- `subject_reference`
- `effective_start`
- `effective_end`
- `code_system`
- `code`
- `display`
- `status`
- `result_observation_record_keys`
- `presented_forms`

### DocumentReference fields

Canonical `DocumentReference` rows include, when present:
- `record_id`
- `record_type`
- `document_reference_id`
- `subject_reference`
- `type_system`
- `type_code`
- `display`
- `status`
- `attachments`

Attachment export is share-safe:
- only structured metadata such as `content_type`, `title`, `size`, and `hash` may be emitted
- attachment payload fields such as raw `data` are excluded
- when an attachment `url` references `Binary/<id>`, the exporter keeps only the structured `binary_id`

### Binary fields

Canonical `Binary` rows include, when present:
- `record_id`
- `record_type`
- `binary_id`
- `content_type`
- `security_context_reference`
- `content_size_bytes`
- `content_sha256`
- `data_present`

Binary export is share-safe:
- raw Binary payload bytes are not emitted
- only stable metadata, derived size/hash values, and structured linkage fields are exported

### Goal and CarePlan fields

Canonical `Goal` rows include, when present:
- `record_id`
- `record_type`
- `goal_id`
- `subject_reference`
- `status`
- `start_date`
- `target_due_date`
- `description`

Canonical `CarePlan` rows include, when present:
- `record_id`
- `record_type`
- `careplan_id`
- `subject_reference`
- `status`
- `intent`
- `period_start`
- `period_end`
- `goal_ids`
- `title`

Canonical `ServiceRequest` rows include, when present:
- `record_id`
- `record_type`
- `service_request_id`
- `subject_reference`
- `status`
- `intent`
- `authored_on`
- `code_system`
- `code`
- `display`
- `performer_references`

Canonical `Coverage` rows include, when present:
- `record_id`
- `record_type`
- `coverage_id`
- `subject_reference`
- `status`
- `type_system`
- `type_code`
- `subscriber_relationship`
- `period_start`
- `period_end`
- `payor_references`

Canonical `Organization` rows include, when present:
- `record_id`
- `record_type`
- `organization_id`
- `name`
- `type_system`
- `type_code`
- `address_city`
- `address_state`
- `address_postal_code`

Canonical `Practitioner` rows include, when present:
- `record_id`
- `record_type`
- `practitioner_id`
- `name`
- `identifier_system`
- `identifier_value`

Canonical `Location` rows include, when present:
- `record_id`
- `record_type`
- `location_id`
- `name`
- `address_city`
- `address_state`
- `address_postal_code`

Canonical `ImagingStudy` rows include, when present:
- `record_id`
- `record_type`
- `imaging_study_id`
- `subject_reference`
- `status`
- `started`
- `series_summary`

Canonical `Specimen` rows include, when present:
- `record_id`
- `record_type`
- `specimen_id`
- `subject_reference`
- `collected_time`
- `received_time`
- `type_system`
- `type_code`
- `display`
- `identifiers`

Canonical `Device` rows include, when present:
- `record_id`
- `record_type`
- `device_id`
- `patient_reference`
- `status`
- `type_system`
- `type_code`
- `display`
- `manufacturer`
- `identifiers`

Canonical `Provenance` rows include, when present:
- `record_id`
- `record_type`
- `provenance_id`
- `recorded`
- `agent_references`
- `target_references`
- `target_record_keys`
- `canonical_person_id` resolution:
  - preferred: `subject.reference == "Patient/<id>"` matched against identity aliases (`fhir:id`)
  - fallback: if exactly one person exists in `data/identity/people.json`, use that person
  - otherwise: `"unresolved"`

### CDA XML (`export_cda.xml`)
- Stream-parses `<observation>` elements and emits minimal observation-like rows when available:
  - `effectiveTime@value` → `event_time` (parsed as UTC when format is `YYYYMMDDHHMMSS`)
  - `code@code`
  - `value@value` / `value@unit`
- Skipped (MVP): narrative text, full section semantics, non-observation entries, and any attempt at comprehensive CDA coverage.

## Determinism rules

The exporter is deterministic for the same input + identity + mode:
- Per-record `event_key` is derived from a stable JSON payload (sha256) and used to dedupe within a run.
- `record_key` is the canonical name for the stable per-record key (currently equal to `event_key`).
- Per-stream ordering is a stable sort by:
  - `event_time`, `canonical_person_id`, `source`, `source_file`, `source_id`, `event_key`
- Per-line JSON serialization uses:
  - sorted keys (`sort_keys=True`)
  - stable separators (`separators=(",", ":")`)
- Outputs are written via a temp file and atomically replaced.
