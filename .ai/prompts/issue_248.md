Issue #248: Refresh Apple Health bootstrap dataset on mail server

Source of truth: GitHub Issue #248

Scope:
- Download the private Drive export.zip outside the repository.
- Validate checksum and ZIP structure without exposing archive contents.
- Profile and process the Apple Health bootstrap on the recovered mail server.
- Preserve the previous current dataset as a rollback target.
- Install the refreshed dataset under /opt/healthdelta/data/datasets and verify live authenticated backend endpoints.

Non-goals:
- No backend image deployment.
- No application code changes.
- No iOS application changes.
- No publication of private health data to GitHub, CI artifacts, or the repository.
