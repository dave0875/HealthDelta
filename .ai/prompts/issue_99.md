---
Story
As a CI operator,
I want the Issue footer checker to tolerate force-push history rewrites,
So that governance checks do not fail when branch history is rebased.

Context / Why
We allow rebases and force-pushes. The current check assumes the "before" SHA is still present, causing CI to fail on push events after history rewrites.

Acceptance Criteria
- Given a force-pushed branch, when CI runs the Issue footer check, then it resolves a safe commit range without crashing.
- Given a normal push, when CI runs the Issue footer check, then it inspects the correct commit range.
- The check continues to require an Issue footer in every commit message.

Out of Scope
- Changing policy to disallow rebases or force-pushes.
- Altering Issue footer formatting requirements.

Notes
- Use merge-base fallbacks when the "before" SHA is missing.
---
