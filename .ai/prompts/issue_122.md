---
Story
As a maintainer,
I want a Jetson Orin model/runtime decision matrix,
So that local-only inference is feasible within device memory/latency constraints.

Context / Why
Orin deployment needs explicit tradeoff decisions (accuracy, latency, memory, GPU use) for summaries and risk flags first, then trends/Q&A. Without a matrix, implementation can stall or select incompatible models.

Acceptance Criteria
- Given Orin Nano Super constraints, when planning is completed, then a ranked model/runtime matrix is documented (primary + fallback CPU path).
- Given target workloads (summary, risk flags, trend, Q&A), when sizing is documented, then expected latency/memory envelopes are specified per workload.
- Given local-only/privacy constraints, when architecture notes are produced, then no cloud dependencies are included.
- Given CI evidence requirements, when this issue is merged, then planning artifacts are persisted and referenced from docs.

Out of Scope
- Model benchmarking implementation.
- Runtime optimization code.

Notes
- Prefer quantized, ARM64-compatible options with CUDA/TensorRT compatibility where practical.
---
