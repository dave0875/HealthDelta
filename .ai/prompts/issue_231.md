Issue: #231

Title: Backfill live ORIN cumulative dataset from saved iPhone exports

GitHub Issue URL: https://github.com/dave0875/HealthDelta/issues/231

Prompt
- Rebuild the live ORIN cumulative dataset by replaying the saved iPhone export directories that already exist on the MacBook Air.
- Replay the runs oldest-to-newest through the deployed ORIN upload API so the live service exercises the cumulative upload path exactly as operators will use it.
- Preserve duplicate-safe semantics so overlapping incremental uploads do not double count rows.
- Prove the live ORIN current dataset now reflects the cumulative replay and that `/insights/current` returns `status=ok` against that cumulative dataset.
