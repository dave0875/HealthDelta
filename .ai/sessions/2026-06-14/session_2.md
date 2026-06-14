# Session 2 - Issue #260

Date: 2026-06-14
Issue: #260 - Repair and ingest malformed large export_cda.xml without excluding CDA

Goals
- Replace the current CDA-exclusion workaround with a best-effort streaming repair path.
- Keep CDA-derived profile, NDJSON, and report signal instead of discarding the file.
- Fail clearly on obvious truncation and direct resubmission to `dave0875@gmail.com`.

Progress
- Opened Issue #260 with the required story template.
- Audited the current CDA pipeline and confirmed three full-file assumptions that are not viable for a 5+ GB CDA:
  - `profile.py` uses `iterparse` directly on the malformed raw file and fails on the premature close.
  - `ndjson_export.py` uses `ET.parse(...).getroot()`, which requires loading the full CDA DOM.
  - `deid.py` reads the entire CDA file into memory and reparses it as a DOM.
- Inspected the live malformed file on GORF without copying private data into the repo.
- Confirmed the actual defect is recoverable: a premature `</ClinicalDocument>` appears around line 11055, more `<component>` content follows, and the file never writes a final root close at EOF.
- Captured the additional requirement that obvious truncation must fail clearly and instruct resubmission to `dave0875@gmail.com`.

Next step
- Add failing tests for recoverable malformed CDA and unrecoverable truncated CDA, then implement a streaming repair layer and route profile/deid/NDJSON through it.

Verification
- Added focused tests for:
  - recoverable malformed CDA repair
  - truncation failure with resubmission guidance
  - profile on repaired CDA
  - NDJSON export on repaired CDA
  - de-id on repaired CDA
- Verified with:
  - `python3 -m unittest tests.test_cda_xml tests.test_profile.TestExportProfile.test_export_profile_repairs_recoverable_cda tests.test_profile.TestExportProfile.test_export_profile_fails_clearly_on_truncated_cda tests.test_ndjson_export_malformed_cda tests.test_deid_malformed_cda -v`
