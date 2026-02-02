---
Story
As an operator,
I want backend release builds to include the synthetic ORIN smoke fixture,
So that deploy verification endpoints can run reliably on tagged releases.

Context / Why
Tag `v0.0.6` release backend image failed because Docker build context excluded `tests/` while Dockerfile tried to copy `tests/fixtures/profile_export`.

Acceptance Criteria
- Given a release build, when Docker image builds, then synthetic fixture copy succeeds without relying on excluded paths.
- Given ORIN deploy verification, when `/summary` and `/qa` checks run, then fixture path is available in-container.
- Given CI/release evidence, when a new tag is pushed, then Release and Deploy Backend (ORIN) workflows both succeed.

Out of Scope
- Changing verification semantics beyond fixture path correctness.
- Adding new runtime dependencies.

Notes
- Keep fixture share-safe and minimal.
---
