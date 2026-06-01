# Issue 251 Prompt

Fix the ORIN backend benchmark workflow dependency bootstrap discovered after the
mail-server baseline refresh. The self-hosted runner must create an isolated
Python environment, install HealthDelta dependencies, run the benchmark and
threshold checker with that environment, and upload the existing benchmark
artifact. Do not change thresholds, deploy an image, or change private data.
