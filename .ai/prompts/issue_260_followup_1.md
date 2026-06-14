Issue: #260 Follow-up 1
Date: 2026-06-14

This follow-up does NOT change issue scope or acceptance criteria.

Execution constraints
- The real malformed file on GORF closes `</ClinicalDocument>` prematurely around line 11055, continues with more `<component>` content, and never writes a final `</ClinicalDocument>` at EOF.
- Recoverable structure defects like that should be repaired in a streaming derived copy.
- If the CDA appears obviously truncated rather than merely malformed, the application must fail clearly and direct the operator to resubmit the file and notify `dave0875@gmail.com`.
