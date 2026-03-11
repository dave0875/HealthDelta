# Session 6

- Date: 2026-03-11
- Issue: #223
- Goal: Remove the runner-dependent race in the existing macOS dashboard progress tests so Issue #223 can satisfy CI proof.

Actions
- Investigated the hanging macOS simulator job and confirmed the run stalled inside `DashboardViewModelTests` while waiting on a gate-backed upload test.
- Identified the race: the tests assumed a single `Task.yield()` was enough for the async gate to become blocked before assertions and resume.
- Added an explicit gate-start synchronization path so the tests wait until the exporter/uploader is actually suspended before asserting progress state and resuming the gate.
