Issue: #230

Title: Accumulate iPhone incremental uploads on ORIN instead of replacing current state

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/230

Prompt
- Change ORIN upload finalization so incremental iPhone uploads accumulate into a cumulative current dataset instead of replacing prior state.
- Preserve the raw uploaded run so provenance and reconstruction remain possible.
- Build the cumulative current dataset in a duplicate-safe way so re-uploading the same iPhone run does not double count rows.
- Make `/insights/current` analyze the cumulative current dataset by default after uploads.
- Add focused tests that prove cumulative behavior, duplicate-safe merging, and current-dataset visibility through the existing upload/backend APIs.
