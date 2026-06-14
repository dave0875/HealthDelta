Issue: #259 Follow-up 2
Date: 2026-06-14

This follow-up does NOT change issue scope or acceptance criteria.

Execution constraints
- The live rerun may reuse the same build directory because the Drive file ID is stable across retries.
- Excluded ZIP members must not survive from a prior failed attempt in the derived processing tree.
- The retry path must therefore recreate the derived extraction tree from scratch before unpacking the raw ZIP, then rerun the live `GORF` service and verify whether `mail` promotes.
