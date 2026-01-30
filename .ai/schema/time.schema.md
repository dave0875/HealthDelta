# TIME Tracking Schema

This document defines the schema for the `time.csv` file.
This data is used for billing and accounting purposes.

## Columns

- `date`: ISO-8601 format (YYYY-MM-DD)
- `issue_id`: The ID of the issue being worked on.
- `client`: The client the work is for.
- `minutes`: The number of minutes spent on the task.
- `agent`: The agent performing the work.
  - `human`
  - `codex`
  - `gemini`
  - `other`
- `activity`: The type of activity.
  - `design`
  - `impl`
  - `test`
  - `docs`
  - `ops`
- `notes`: Optional notes about the work.
