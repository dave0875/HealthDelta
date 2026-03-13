Issue: #242
Title: Recover richer clinical signal from original Apple export and reprocess ORIN baseline

Objective
- Reprocess the original Apple export archive so recent clinical activity preserves as much source labeling as possible and can be summarized as meaningful labs, vitals, and structured findings instead of anonymous unit buckets.
- Keep disk usage bounded by pruning large temporary artifacts once the richer baseline has been validated.

Acceptance anchors
- Reprocessing from the original Apple export preserves materially richer clinical labels where the source provides them.
- A last-2-month clinical summary can describe recognizable clinical happenings with better fidelity than anonymous unit buckets alone.
- Temporary scratch artifacts created during reprocessing are pruned once they are no longer needed.
- CI and Release remain green.
