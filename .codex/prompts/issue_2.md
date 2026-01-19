# issue_2

Issue: https://github.com/dave0875/HealthDelta/issues/2

Prompt (verbatim)

```
CI / Test Execution Proof (Mandatory):

1) Use my MacBook Pro as a self-hosted GitHub Actions runner.
   - Label it: self-hosted, macOS, xcode
   - This runner is the authoritative environment for all Xcode-related work.

2) Establish two GitHub Actions workflows immediately (issue-driven, no code changes without issues):

   A) ci.yml (runs on every push and PR)
      - Job 1: ubuntu-latest
        * Run all non-iOS tests:
          - export.zip bootstrap parsing
          - canonical identity + name parsing logic
          - NDJSON schema validation
          - DuckDB ingestion and deduplication
        * These tests must be fast, deterministic, and headless.

      - Job 2: self-hosted macOS runner (MacBook Pro)
        * Run `xcodebuild test` targeting iPhone Simulator
        * Upload the full .xcresult bundle as a build artifact
        * If feasible, also export JUnit so GitHub shows test counts/failures
        * A green checkmark here is required before merge.

   B) device_smoke.yml (manual workflow_dispatch only)
      - Runs on the self-hosted macOS runner
      - Builds and optionally runs on a physically connected iPhone
      - Purpose: entitlement sanity, HealthKit permissions, “does it actually run”
      - This is NOT required for every PR, but must be runnable and documented.

3) Test execution proof is non-negotiable.
   - CI logs, artifacts, and test results are the proof of correctness.
   - Any story whose acceptance criteria include “works” must also include
     “CI passes with published artifacts.”

4) Update documentation:
   - Add docs/runbook_xcode.md describing:
     * self-hosted runner setup on the MacBook Pro
     * required Xcode version
     * simulator runtimes
     * how to run workflows locally or re-trigger them
   - Reference this runbook from AGENTS.md.

5) Issue discipline applies to CI work.
   - Creating or modifying workflows requires a GitHub issue capturing WHY.
   - CI-related acceptance criteria must explicitly name which workflow/job proves success.
   - Record Codex prompts, CI design decisions, and runner rationale in .codex/
     (prompts/, sessions/, and ADRs as appropriate).

Proceed by:
- Creating the necessary GitHub issues (using the mandatory story template),
- Recording the prompts used to define CI in .codex/prompts/,
- Logging time and LLM usage in TIME.csv,
- And only then implementing workflows.

Do not skip steps, do not bundle CI changes with unrelated work, and do not rely on “trust me” instead of CI artifacts.
```

