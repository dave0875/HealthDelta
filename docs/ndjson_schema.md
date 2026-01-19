# NDJSON Schema (Draft)

## Requirements (current)
- Append-only NDJSON with upsert + delete events.
- Partition by `person_key`, `stream`, `type/resourceType`, and day.
- Compressed (gzip minimum) and chunked for high volume.
- Must not contain names, source patient IDs, or contact details.

## TODO
- Define event envelope + validation strategy.

