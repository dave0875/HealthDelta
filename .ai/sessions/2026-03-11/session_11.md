# Session 11

- Date: 2026-03-11
- Issue: #227
- Goal: Package the runtime dependencies required by the ORIN artifact-grounded insights path into the backend image.

Actions
- Confirmed the live ORIN backend container does not have `duckdb` installed and therefore cannot execute the new `/insights/current` analysis path even if rolled forward to current `main`.
- Traced the gap to the backend `Dockerfile`, which copies source files but does not install the project's declared Python dependencies from `pyproject.toml`.
- Scoped the fix to reproducible image packaging and release verification rather than ad hoc host-side package installation.
