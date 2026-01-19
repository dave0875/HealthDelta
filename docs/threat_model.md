# Threat Model (Draft)

## Assets
- Private health data (fitness + clinical).
- Identity link state (`PersonLink`) and anchors.

## Threats (starting list)
- Identity confusion / unintended merges.
- Accidental leakage of PII into exports or logs.
- Incorrect incremental logic causing duplication or loss.

## TODO
- Define trust boundaries, storage/transport encryption expectations, and logging redaction rules.

