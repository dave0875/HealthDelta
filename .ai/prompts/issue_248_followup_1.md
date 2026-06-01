Issue #248 follow-up 1: Process the private baseline on GORF due to mail memory limits

This follow-up does NOT change issue scope or acceptance criteria.

Execution constraint:
- mail has 7.4 GiB RAM and cannot complete the current non-streaming de-identification or NDJSON accumulation paths for the 2.54 GB export.xml.
- Preserve the received Drive ZIP unchanged.
- Derive a private working tree that excludes only the malformed export_cda.xml member.
- Run share-mode processing on GORF outside the repository, then transfer the completed private baseline artifacts to mail.
- Keep the live mail dataset pointer unchanged until verification is complete.
