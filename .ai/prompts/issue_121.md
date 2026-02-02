---
Story
As an operator,
I want a deterministic inventory of `~/export` data types and sensitive fields,
So that Orin deployment sizing and de-identification rules are evidence-based.

Context / Why
The super prompt requires analysis of PDFs/JSON/Apple exports and PHI/PII field mapping before architecture choices. Without this, model and storage decisions for Orin are guesses and can leak sensitive data.

Acceptance Criteria
- Given a representative export fixture set, when inventory tooling runs, then it produces share-safe counts by type, size distribution, and largest-file report.
- Given Apple Health JSON samples, when schema profiling runs, then it outputs observed keys/structures and cardinality summary.
- Given identified sensitive fields, when redaction strategy is documented, then field-level handling rules are explicit and testable.
- Given CI governance, when this issue is merged, then test logs and inventory artifacts are uploaded as deterministic evidence.

Out of Scope
- Building model inference.
- Production deployment execution.

Notes
- Must not persist PHI-containing raw samples in git.
- Output artifacts must be share-safe.
---
