# Ingest Runbook (Bootstrap Staging)

## Goal
Stage an Apple Health export into a deterministic run directory with a manifest and layout file so downstream work can build incrementally on stable artifacts.

## Install (provides the `healthdelta` CLI)
From the repo root:

- `python3 -m venv .venv`
- `. .venv/bin/activate`
- `pip install -e .`

## Command

- `healthdelta ingest --input <path> [--out data/staging]`

Where `--input` is either:
- a path to `export.zip`, or
- a path to an unpacked export directory containing `export.xml` (clinical JSONs are discovered as `*.json` under the directory).

## Output layout
Each run writes to:
- `data/staging/<run_id>/`

Files written:
- `data/staging/<run_id>/manifest.json`
- `data/staging/<run_id>/layout.json`
- plus staged copies under `data/staging/<run_id>/source/`

## Determinism notes

`run_id` derivation (documented in `manifest.json`):
- zip input: `sha256(export.zip bytes)`
- directory input: `sha256(relpath + sha256(file bytes))` over `export.xml` and all discovered `*.json` files (sorted by relative path)

Determinism rule:
- Same input bytes => same `files[*].sha256` values.
- Time-varying fields live under `manifest.json.timestamps.*` (non-deterministic by design).

## Privacy / path redaction
`manifest.json.input` is redacted by default to avoid persisting local machine paths.

