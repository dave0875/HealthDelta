Issue: #259
Title: Ops: automate full baseline refresh from Drive HEALTH/Exports into mail

Objective
- Add an operator-visible automation path on GORF that watches the prior Drive source for `export.zip`, builds the full baseline on GORF, and promotes a verified dataset to `mail`.
- Keep the raw export unchanged, preserve rollback, and avoid rebuilding the large baseline on `mail`.

Acceptance anchors
- A one-shot automation script detects whether the watched Drive export is newer than the last processed file.
- When a new export is present, the script downloads it privately, runs the established GORF-side profile/build/validate flow, assembles a `mail`-ready dataset bundle, copies it to `mail`, and verifies the live endpoints after promotion.
- When no new export is present, the script exits successfully without mutating `mail`.
- Operator documentation covers prerequisites, configuration, systemd timer setup, execution, and rollback.
- No secrets or private health data are added to the repository.
