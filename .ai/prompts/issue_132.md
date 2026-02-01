---
Story
As a maintainer,
I want a reproducible ORIN runner diagnostics proof job,
So that we can verify GitHub scheduling and runtime prerequisites on `self-hosted, linux, orin` before deployment.

Context / Why
Current ORIN deployment capability is documented but unproven by recent runs. We need a safe, idempotent diagnostics workflow that demonstrates runner scheduling and captures machine evidence artifacts.

Acceptance Criteria
- Given a workflow dispatch, when diagnostics run, then job executes on `runs-on: [self-hosted, linux, orin]`.
- Logs include `uname -a`, `arch`, `docker --version`, and `docker compose version`.
- A deterministic artifact `orin-runner-env` is uploaded containing `env.txt` with those values.
- Diagnostics run does not attempt deployment and is safe to rerun.

Out of Scope
- Image publishing changes.
- Container deployment actions.

Notes
- Keep implementation tightly scoped to runner proof only.
---
