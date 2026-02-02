# ORIN local model/runtime matrix (Issue #122)

This planning artifact ranks local-only runtime options for `orin.local` and sets workload envelopes for backend implementation.

Issue: #122

## Constraints (authoritative for this phase)
- Target host: Jetson Orin (ARM64 Linux, CUDA-capable GPU, shared memory budget).
- Privacy: local-only inference; no cloud model calls, no third-party hosted embeddings.
- Reliability: deterministic fallback must exist when GPU runtime is unavailable.
- Deployment compatibility: artifacts must remain ARM64-compatible and container-friendly.

## Ranked runtime options

1) `llama.cpp` (ARM64 build, CUDA/cuBLAS enabled when available)
   - Why first: mature quantized GGUF support, strong ARM64 portability, same runtime can run GPU or CPU fallback.
   - Primary use: summaries, risk flags, trend narrative generation, grounded Q&A response synthesis.

2) ONNX Runtime + TensorRT EP (selective model path)
   - Why second: useful for smaller classification-style models when we need predictable latency.
   - Primary use: optional risk-flag scoring model path (non-generative) if later benchmarking justifies complexity.

3) TensorRT-LLM (deferred)
   - Why third: potentially best throughput but highest operational complexity for current scope.
   - Primary use: future optimization track after MMF behavior is proven with simpler runtime.

## Workload matrix (ranked primary + CPU fallback)

| Workload | Primary runtime/model plan | CPU fallback plan | Target latency envelope | Memory envelope (planning) |
|---|---|---|---|---|
| Doctor-style summary | `llama.cpp` + 3B instruct GGUF (Q4/Q5) | same model/runtime CPU-only | p50 <= 3s, p95 <= 8s per request | GPU path <= 6 GiB total, CPU path <= 8 GiB RSS |
| Risk flags v1 (rule + explanation) | Rules engine + `llama.cpp` 3B for rationale text | rules-only output + optional short CPU rationale | rules <= 1s, full response p95 <= 5s | <= 4 GiB for explanation path |
| Trend analysis v1 | `llama.cpp` 3B/7B quantized (bounded context) | 3B CPU-only with reduced context | p50 <= 5s, p95 <= 12s | <= 7 GiB (GPU), <= 8 GiB (CPU) |
| Grounded Q&A v1 (abstain-capable) | retrieval + `llama.cpp` 3B synthesis | retrieval + template/rules abstain response | retrieval <= 1.5s, full p95 <= 8s | <= 6 GiB with retrieval cache |

## Local-only architecture notes
- Retrieval/indexing stays local (DuckDB + local text index path); no external vector DB SaaS.
- Prompt orchestration stays in backend service containers on ORIN.
- Model assets are versioned as local deploy dependencies and referenced by release-tagged backend deployments.
- Fallback mode is explicit: if GPU path is unavailable, service remains operable in degraded CPU mode.

## Decision for MMF implementation sequence
- Implement with `llama.cpp` as the single mandatory runtime for Issues #123-#126.
- Keep ONNX/TensorRT as optional optimization tasks only after MMF acceptance criteria pass.
- Preserve one code path for prompt/guardrail logic so runtime swaps do not change behavior contracts.

## Validation hooks for downstream issues
- Each workload issue must publish p50/p95 latency and memory observations against this matrix.
- CI/deploy artifacts must record runtime mode (`gpu` or `cpu-fallback`) and model id/hash.
- Any deviation from envelopes requires issue-level note and explicit follow-up issue.
