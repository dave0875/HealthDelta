Issue: #259 Follow-up 1
Date: 2026-06-14

This follow-up does NOT change issue scope or acceptance criteria.

Execution constraints
- The watched Drive source may contain multiple ZIP filenames, not only `export.zip`; the automation should continue selecting the newest ZIP in `HEALTH/Exports`.
- The previously validated malformed-member workaround must work for nested archive paths as they appear in Apple export ZIPs, while preserving the raw downloaded ZIP unchanged.
- Prove the fix with focused tests, then rerun the live `GORF` systemd user service and verify whether promotion reaches `mail`.
