# issue_5

Issue: https://github.com/dave0875/HealthDelta/issues/5

Prompt (verbatim)

```
Open a NEW GitHub issue (#5) using the story template.

Title:
Identity bootstrap: canonical person registry + name parsing (First Last vs Last, First)

Story:
As a HealthDelta maintainer,
I want a canonical person registry that gracefully links records from multiple health systems to the same person,
so that consumers never see confusing duplicate “patients” when identifiers differ across sources.

Acceptance Criteria:
- Implement `healthdelta identity build --input data/staging/<run_id>` that produces:
  - `data/identity/people.json` (canonical people)
  - `data/identity/aliases.json` (observed name variants + source refs)
- Matching rule (initial, explicit):
  - treat the person as the same if BOTH first name and last name match after normalization
  - system must recognize "<first> <last>" vs "<last>, <first>" correctly
  - normalization: trim, collapse whitespace, casefold; ignore middle names/initials for now (document)
- Must handle multiple patient IDs across sources without confusion:
  - store all observed external IDs as aliases under one canonical person
  - never overwrite; always append provenance
- Provide unit tests covering:
  - parsing formats
  - normalization edge cases
  - two different people with same last name but different first name
- Update docs:
  - `docs/runbook_identity.md` and reference from AGENTS.md
- Record `.codex/prompts/issue_5.md` (immutable) and TIME.csv entries

Constraints:
- No de-identification yet.
- No DuckDB schema yet.
- Use only staged outputs from Issue #4 (manifest/layout) as inputs.
- All repo mutations on GORF only.

Close Issue #5 only when CI is green.
```

