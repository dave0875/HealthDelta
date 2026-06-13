# Runbook: Automated Full Baseline Refresh via GORF -> mail

This runbook describes the automated path for watching the Google Drive source used in the June 1 baseline refresh and promoting a verified full baseline to `mail`.

## Purpose

Use this path when you need `mail` to analyze the newest full Apple Health export, including records that do not flow through the iPhone incremental upload path.

Why this path exists:
- the prior validated source was Drive path `HEALTH/Exports/export.zip`
- the full baseline must be built on `GORF`
- `mail` is the serving target, not the large-export build host

## Script

One-shot refresh command:

```bash
python3 scripts/mail_drive_refresh.py \
  --drive-source 'gdrive:HEALTH/Exports/export.zip' \
  --work-root "$HOME/private/healthdelta_mail_refresh" \
  --repo-root "$HOME/Code/HealthDelta" \
  --state-json "$HOME/private/healthdelta_mail_refresh/state.json" \
  --mail-host mail \
  --mail-data-root /opt/healthdelta/data \
  --verify-base-url http://127.0.0.1:8080 \
  --print-json
```

The script:
- checks the remote export fingerprint via `rclone lsjson`
- exits cleanly with `status=no_changes` if the remote export matches the last processed file
- downloads the new `export.zip` unchanged to a private work area on `GORF`
- verifies ZIP integrity
- extracts a derived processing tree
- runs:
  - `healthdelta export profile`
  - `healthdelta export coverage`
  - `healthdelta run all --mode share`
  - `healthdelta export validate`
- assembles a `mail`-ready dataset bundle containing:
  - `export.zip`
  - `analysis/duckdb/run.duckdb`
  - `analysis/reports/summary.json`
  - `analysis/reports/summary.md`
  - `analysis/note/doctor_note.md`
- copies that bundle to `mail`
- atomically repoints `datasets/current`
- verifies:
  - `/healthz`
  - authenticated `/datasets/current`
  - authenticated `/patients/current`
  - authenticated `/insights/current`

## Prerequisites

On `GORF`:
- `rclone` installed and configured with a remote that can access the private Drive source
- repo checkout available locally
- Python environment able to run `python -m healthdelta`
- `rsync`
- `ssh` access to `mail`

On `mail`:
- backend deployed and healthy
- `HEALTHDELTA_UPLOAD_TOKEN` present in `/opt/healthdelta/.env`
- writable `/opt/healthdelta/data/datasets`

## Optional malformed-member exclusion

If the incoming export has a known-bad ZIP member that must be excluded from the derived processing tree while preserving the raw ZIP unchanged, pass one or more exclusions:

```bash
python3 scripts/mail_drive_refresh.py \
  ... \
  --exclude-member export_cda.xml
```

This matches the prior manual baseline-refresh constraint where the raw received ZIP remained unchanged but the derived work tree omitted the malformed member.

## Suggested automation cadence

Run the script as a user-level systemd timer on `GORF` or from `cron`. A 15-minute cadence is sufficient.

Example `systemd --user` service:

```ini
[Unit]
Description=HealthDelta mail baseline refresh

[Service]
Type=oneshot
WorkingDirectory=%h/Code/HealthDelta
ExecStart=%h/Code/HealthDelta/.venv/bin/python scripts/mail_drive_refresh.py \
  --drive-source gdrive:HEALTH/Exports/export.zip \
  --work-root %h/private/healthdelta_mail_refresh \
  --repo-root %h/Code/HealthDelta \
  --state-json %h/private/healthdelta_mail_refresh/state.json \
  --mail-host mail \
  --mail-data-root /opt/healthdelta/data \
  --verify-base-url http://127.0.0.1:8080
```

The same unit templates are checked into the repo at:
- `deploy/gorf/healthdelta-mail-refresh.service`
- `deploy/gorf/healthdelta-mail-refresh.timer`

Install them with:

```bash
mkdir -p ~/.config/systemd/user
ln -sf ~/Code/HealthDelta/deploy/gorf/healthdelta-mail-refresh.service ~/.config/systemd/user/healthdelta-mail-refresh.service
ln -sf ~/Code/HealthDelta/deploy/gorf/healthdelta-mail-refresh.timer ~/.config/systemd/user/healthdelta-mail-refresh.timer
systemctl --user daemon-reload
systemctl --user enable --now healthdelta-mail-refresh.timer
```

Example timer:

```ini
[Unit]
Description=Poll Drive for a new HealthDelta baseline export

[Timer]
OnBootSec=5m
OnUnitActiveSec=15m
Persistent=true

[Install]
WantedBy=timers.target
```

## State and outputs

The script keeps all private artifacts under `--work-root`, including:
- downloaded raw ZIP
- derived input tree
- HealthDelta build outputs
- assembled `mail` bundle
- state file tracking the last processed remote export

The state file contains:
- last processed remote fingerprint
- last promoted dataset name
- last local run root
- last promotion output

## Rollback

The script prints the prior dataset name as `rollback_dataset=...` during promotion.

Manual rollback remains:

```bash
ssh -F /dev/null mail '
  cd /opt/healthdelta/data/datasets &&
  rm -f current current.txt &&
  ln -s <previous_dataset_name> current
'
```

Then verify:

```bash
ssh -F /dev/null mail '
  cd /opt/healthdelta
  . ./.env
  curl -fsS http://127.0.0.1:8080/healthz
  echo
  curl -fsS -H "authorization: Bearer $HEALTHDELTA_UPLOAD_TOKEN" http://127.0.0.1:8080/datasets/current
'
```

## Safety rules

- Never commit raw exports, private work trees, or mail datasets to Git.
- Preserve the downloaded `export.zip` unchanged.
- Use `GORF` for the full baseline build; do not move that heavy build onto `mail`.
- Keep the previous dataset directory on `mail` until verification passes.
