---
Story
As a maintainer,
I want ORIN deploy automation to run without sudo,
So that deployment does not hang on non-interactive password prompts.

Context / Why
The ORIN deploy script currently attempts `sudo mkdir`/`sudo chown` when the deploy directory is missing. On self-hosted runner hosts this can block indefinitely waiting for a password. We already use a one-time directory bootstrap process, so deploy should fail fast with a clear remediation message instead of invoking sudo.

Acceptance Criteria
- Given `/opt/healthdelta` exists and is writable by the runner user, when ORIN deploy runs, then no sudo commands are executed.
- Given `/opt/healthdelta` is missing, when ORIN deploy runs, then the script exits quickly with a clear one-time setup instruction.
- Runbook docs state the deploy directory must be pre-created/chowned and that deploy workflow does not use sudo.
- CI remains green for the repository checks.

Out of Scope
- Changing ORIN host sudoers policy.
- Feature changes to backend service behavior.

Notes
- This is Option A: pre-create/chown deploy dir once, then run deploy without sudo.
---
