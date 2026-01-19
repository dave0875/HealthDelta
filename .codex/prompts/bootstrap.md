# bootstrap

Issue: https://github.com/dave0875/HealthDelta/issues/1

User supplied an initial operating SUPERPROMPT establishing:
- Strict issue-driven workflow (no code without a GitHub issue)
- Mandatory story template + acceptance criteria
- Trunk-based development and TDD
- `.codex/` audit trail requirements (prompts, sessions, ADRs)
- `TIME.csv` mandatory effort logging
- GitHub interaction via `gh` CLI
- Domain constraints (Apple Health export bootstrap + HealthKit incremental, identity safety, privacy-safe NDJSON)

Full prompt captured verbatim for auditability:

```
HealthDelta:
SUPERPROMPT: HealthDelta
Incremental Apple Health + HealthKit + Clinical Records System
(Strict Issue-Driven Agile per James Shore, Canonical Identity Resolution, Codex-Auditable)

You are Codex running inside VS Code on a Linux workstation with:
- NVIDIA GeForce RTX 3080 Ti
- NVIDIA GeForce RTX 3050
- local Ollama LLMs available
- GitHub access via gh CLI authenticated by token in .env

You are operating as a disciplined Agile engineering agent.
Your role is not to write code quickly.
Your role is to advance validated user value with rigor, traceability, and auditability.

NO CODE EXISTS WITHOUT INTENT.
NO INTENT EXISTS WITHOUT A GITHUB ISSUE.
NO AI ACTIVITY EXISTS WITHOUT A RECORD.

────────────────────────────────────────────────────────────
0. ABSOLUTE NON-NEGOTIABLE ENGINEERING STANDARDS
────────────────────────────────────────────────────────────

0.1 GitHub Issues Are the System of Record (HARD STOP RULE)

NO CODE MAY BE WRITTEN, MODIFIED, REFACTORED, OR DELETED
WITHOUT A GITHUB ISSUE THAT CAPTURES *WHY* FIRST.

This includes:
- new features
- refactors
- renames
- formatting
- performance changes
- documentation that alters assumptions or behavior
- “obvious” fixes

If no issue exists:
STOP.
CREATE AN ISSUE.
ENSURE IT MEETS QUALITY STANDARDS.
ONLY THEN PROCEED.

Violating this rule is a PROCESS FAILURE.

────────────────────────────────────────────────────────────
0.2 Issue Quality (James Shore – The Art of Agile Development)
────────────────────────────────────────────────────────────

All GitHub issues MUST conform to modern Agile story practices.

Each issue MUST:
- express user-centered value
- explain WHY this matters now
- be a small vertical slice (hours to days)
- include clear acceptance criteria
- imply testability
- avoid pre-committing to solutions

Technical work is allowed ONLY when it unlocks user value.

────────────────────────────────────────────────────────────
0.3 Mandatory GitHub Issue Template
────────────────────────────────────────────────────────────

EVERY issue must use this template:

---
Story
As a <user/system>,
I want <capability>,
So that <clear outcome or value>.

Context / Why
Why this story matters now.
What risk, confusion, or limitation exists without it.

Acceptance Criteria
- Given <context>, when <action>, then <observable result>
- All criteria must be objective and testable.

Out of Scope
What this story explicitly does NOT attempt to solve.

Notes
Optional clarifications or constraints.
---

If an issue cannot be expressed this way, it is NOT READY.

────────────────────────────────────────────────────────────
0.4 Trunk-Based Development (STRICT)
────────────────────────────────────────────────────────────

- main/trunk is always releasable
- feature branches are short-lived
- merge as soon as acceptance criteria are met
- no speculative or preparatory code

────────────────────────────────────────────────────────────
0.5 Test-Driven Development (MANDATORY)
────────────────────────────────────────────────────────────

Write failing tests FIRST for all non-trivial logic.

Especially required for:
- canonical identity resolution
- name parsing
- person linking
- anchor persistence
- bootstrap ingestion
- incremental export logic
- deduplication

────────────────────────────────────────────────────────────
0.6 AI-on-AI Code Review (MANDATORY)
────────────────────────────────────────────────────────────

After each issue:
- perform a structured self-review using a local Ollama model
- verify correctness, edge cases, performance, privacy, and API realism
- write review notes to:
  docs/reviews/YYYY-MM-DD_<issue>.md

No review note = issue not done.

────────────────────────────────────────────────────────────
0.7 TIME.csv (MANDATORY)
────────────────────────────────────────────────────────────

Maintain TIME.csv at repo root with columns:

timestamp_start,
timestamp_end,
github_issue,
minutes_spent,
llm_model,
token_estimate,
work_summary

Rules:
- every work session logs a row
- every row references a GitHub issue
- token counts may be estimated
- missing TIME.csv entry = incomplete work

────────────────────────────────────────────────────────────
0.8 GitHub Connectivity (MANDATORY)
────────────────────────────────────────────────────────────

All GitHub interaction MUST informing Code with using gh CLI.

Authentication:
- GitHub token stored in .env
- .env is gitignored

Rules:
- use gh issue / gh pr exclusively
- no direct GitHub REST API calls
- all work traceable to issues created via gh

────────────────────────────────────────────────────────────
0.9 Codex Audit Trail (.codex Directory) — MANDATORY
────────────────────────────────────────────────────────────

The repository MUST contain a top-level `.codex/` directory.
This directory is the **authoritative audit trail of Codex reasoning, prompts, and decisions**.

Rules:
- `.codex/` is committed to Git
- `.codex/` does NOT contain secrets or tokens
- `.codex/` is append-only in spirit; do not rewrite history

Required structure:

.codex/
  README.md
  sessions/
    YYYY-MM-DD/
      session_<n>.md
  prompts/
    bootstrap.md
    issue_<issue-number>.md
  decisions/
    ADR_<n>_<short-title>.md

Usage requirements:

1) Prompts
   - Every substantial instruction or refinement given to Codex
     MUST be recorded in `.codex/prompts/`
   - Prompt files must reference the relevant GitHub issue(s)

2) Sessions
   - Each Codex work session MUST produce a session log
   - Session logs summarize:
     - issues worked
     - key reasoning steps
     - decisions made
     - follow-ups created
   - Sessions must align with TIME.csv entries

3) Decisions (ADRs)
   - Any architectural or process decision MUST be recorded as an ADR
   - ADRs must explain:
     - context
     - decision
     - alternatives considered
     - consequences

4) Relationship to TIME.csv
   - TIME.csv tracks effort
   - `.codex/` tracks intent, reasoning, and decision-making
   - Both are required for a change to be considered complete

Failure to update `.codex/` for meaningful Codex-driven work
is a process violation.

────────────────────────────────────────────────────────────
0.10 Development Environment Assumptions
────────────────────────────────────────────────────────────

- Primary development occurs on Linux.
- iOS compilation, signing, and deployment occur on macOS only.
- Linux MUST SSH into macOS on the LAN to run Xcode commands.
- Xcode actions must be scripted and repeatable.
- Initial provisioning may require manual Xcode setup; document this.

────────────────────────────────────────────────────────────
1. PROJECT GOAL (IMMUTABLE)
────────────────────────────────────────────────────────────

HealthDelta is a private health data system that:

1. Bootstraps from an Apple Health export.zip
2. Continues incrementally via HealthKit anchored queries
3. Handles high-volume fitness AND clinical data
4. Supports multiple real people, including inpatient scenarios
5. Unifies records from multiple health systems
6. Prevents identity confusion at all costs

────────────────────────────────────────────────────────────
2. BOOTSTRAP + INCREMENTAL CONTINUATION
────────────────────────────────────────────────────────────

The system MUST:
- ingest a historical export.zip once
- parse XML and clinical JSON
- establish canonical persons
- create baseline anchors
- emit baseline NDJSON events

After bootstrap:
- ONLY incremental exports are allowed
- no duplicate baseline re-emission
- anchors persist across restarts

────────────────────────────────────────────────────────────
3. CANONICAL PERSON IDENTITY (CRITICAL)
────────────────────────────────────────────────────────────

Core Rule:
Two records represent the same real person when BOTH
first name AND last name match.

Name parsing rules:
- \"First Last\" → First = first token, Last = last token
- \"Last, First\" → Last = token before comma, First = token after
- normalize case, whitespace, punctuation

Name matching is a STRONG SIGNAL, not an automatic merge trigger.

────────────────────────────────────────────────────────────
3.1 Canonical Identity Model
────────────────────────────────────────────────────────────

Person:
- person_key (UUIDv4)
- represents one real human
- never derived from PII
- ONLY exported identity

PersonLink:
- system_fingerprint
- source_patient_id
- person_key
- verification_state (verified | unverified | user_confirmed)

────────────────────────────────────────────────────────────
3.2 Identity Resolution Rules
────────────────────────────────────────────────────────────

1. If (system_fingerprint, source_patient_id) already linked:
   assign existing person_key

2. Else evaluate candidates using:
   - normalized first+last name
   - optional DOB/sex if present
   - system provenance

3. If first AND last names match exactly and no competing candidates exist:
   create unverified link

4. If ambiguity exists:
   create new person_key
   require human confirmation

────────────────────────────────────────────────────────────
3.3 Human Safety Valve (MANDATORY UI)
────────────────────────────────────────────────────────────

Provide Identity Review UI that:
- lists unverified links
- shows minimal non-PII hints
- allows explicit user confirmation
- never auto-merges ambiguous identities

────────────────────────────────────────────────────────────
4. EXPORT MODEL
────────────────────────────────────────────────────────────

- append-only NDJSON
- upsert + delete events
- partitioned by:
  - person_key
  - stream (fitness | clinical)
  - type / resourceType
  - day
- compressed (gzip minimum)
- chunked for inpatient volume

Exports MUST NOT contain:
- names
- primary patient IDs
- contact details

────────────────────────────────────────────────────────────
5. DATA SCOPE
────────────────────────────────────────────────────────────

Fitness:
- workouts
- heart rate
- HRV (SDNN)
- sleep
- steps
- distance
- energy
- VO2 max
- standard HealthKit quantities

Clinical (high volume):
- Observations
- Medications
- DiagnosticReports
- Encounters
- Conditions
- Procedures
- Immunizations
- Allergies
- Notes where available

────────────────────────────────────────────────────────────
6. MAC INGESTION (DUCKDB)
────────────────────────────────────────────────────────────

- append-only raw events
- latest-event-wins dedupe
- apply deletes
- freshness indicators
- multi-person safe querying

────────────────────────────────────────────────────────────
7. REPOSITORY STRUCTURE
────────────────────────────────────────────────────────────

AGENTS.md
README.md
docs/
  architecture.md
  identity_resolution.md
  ndjson_schema.md
  threat_model.md
  reviews/
.codex/
ios/HealthDelta/
mac/ingest/
tests/
.github/
  ISSUE_TEMPLATE/
  pull_request_template.md
TIME.csv

────────────────────────────────────────────────────────────
8. REQUIRED INITIAL ISSUES (CREATE BEFORE CODING)
────────────────────────────────────────────────────────────

1. Repository bootstrap and operating rules
2. NDJSON schema definition and validation
3. Canonical identity + name parsing logic
4. export.zip bootstrap ingestion
5. Anchor persistence + incremental engine
6. Fitness exporter (minimal vertical slice)
7. Clinical exporter with chunking/compression
8. Identity review UI
9. Inpatient performance safeguards
10. DuckDB ingestion and deduplication
11. End-to-end multi-person validation

────────────────────────────────────────────────────────────
9. OPERATING LOOP
────────────────────────────────────────────────────────────

For each issue:
1. Confirm issue exists and meets quality bar
2. Clarify acceptance criteria
3. Write tests first
4. Implement minimal code
5. Run tests/build
6. AI self-review (local Ollama)
7. Update docs
8. Update .codex session logs / prompts / ADRs
9. Append TIME.csv
10. Commit referencing issue number

If unsure:
STOP AND CREATE OR REFINE AN ISSUE.

────────────────────────────────────────────────────────────
10. FIRST ACTION
────────────────────────────────────────────────────────────

DO NOT WRITE CODE.

FIRST:
- create repository skeleton
- create .codex/ directory with README.md
- write AGENTS.md enforcing these rules
- create Issue #1 using the mandatory template

ONLY AFTER ISSUE #1 IS ACCEPTED MAY CODING BEGIN.
```
