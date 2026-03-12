Issue: #234

Title: Add local-only patient display aliases on iPhone

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/234

Prompt
- Add a local-only patient display alias system on the iPhone so Clinical Compass can show humane labels instead of raw canonical IDs.
- Keep aliases strictly device-local: they must not be exported, uploaded, or included in ORIN requests.
- Let the operator assign or clear an alias for the currently selected patient scope.
- Make aliased patient labels appear in the scope UI and related summary rows.
- Add focused iOS tests for the alias store and the scope-option presentation logic, then verify in the simulator.
