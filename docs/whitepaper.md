# The Bonsai Whitepapers

> **Source documents:**
> [1-bit Bonsai 8B whitepaper](../1-bit-bonsai-8b-whitepaper.pdf) (PrismML, March 2026) &middot;
> [Ternary-Bonsai 8B whitepaper](../ternary-bonsai-8b-whitepaper.pdf) (PrismML, April 2026)

This section distills the two Bonsai whitepapers into a structured technical reference. It is the conceptual anchor for the rest of this repository: every script, binary, model family, and backend documented elsewhere traces back to the ideas explained here.

---

## Table of Contents

1. [Core Thesis and Motivation](#1-core-thesis-and-motivation)
2. [The Bonsai Model Families](#2-the-bonsai-model-families)
3. [Weight Formats and Quantization Schemes](#3-weight-formats-and-quantization-schemes)
4. [The Pareto Frontier and Intelligence Density](#4-the-pareto-frontier-and-intelligence-density)
5. [Cross-Platform Throughput](#5-cross-platform-throughput)
6. [Energy Efficiency](#6-energy-efficiency)
7. [Backend Implementations](#7-backend-implementations)
8. [Benchmark Methodology](#8-benchmark-methodology)
9. [Limitations and Roadmap](#9-limitations-and-roadmap)
10. [Mapping the Whitepapers to the Demo Repo](#10-mapping-the-whitepapers-to-the-demo-repo)

---

## 1. Core Thesis and Motivation

**The central problem is deployment, not training.** The whitepapers argue that the defining constraint in modern AI is no longer whether powerful models can be trained, but whether they can be deployed reliably, affordably, and at scale. In production systems, *inference* dominates real-world cost, energy use, and latency.

*(1-bit whitepaper, Section 1 "Executive Summary"; Section 2 "Efficiency as the Defining Constraint in AI Deployment")*

### Why Memory Bandwidth Matters More Than Compute

During autoregressive token generation (one token at a time), the bottleneck is **memory bandwidth** --- the cost of streaming the full model weight matrix from memory for every generated token. Peak arithmetic throughput is secondary. This means that *reducing weight precision directly reduces the main bottleneck*: fewer bits per weight = less memory traffic per token = faster generation and lower energy.

*(1-bit whitepaper, Section 2 "Memory Bandwidth Is the Real Bottleneck")*

### Why 1-Bit Has Been Hard

Binary-weight neural networks have been studied for decades, but prior attempts at sub-4-bit quantization for LLMs suffered from:

- **Qualitative (not gradual) degradation** --- models remained fluent but became brittle on multi-step reasoning, tool use, and edge cases.
- **Operational complexity** --- curated calibration sets, auxiliary metadata, custom layer handling, and bespoke runtimes that did not integrate with standard inference stacks.

PrismML's approach is based on *mathematically grounded* proprietary Caltech IP rather than ad hoc heuristics, enabling end-to-end 1-bit weight precision across the *full* network (embeddings, attention projections, MLP projections, and LM head) without higher-precision escape hatches.

*(1-bit whitepaper, Section 2 "Why 1-Bit Has Remained Out of Reach"; Section 3 "What Makes PrismML Different")*

---

## 2. The Bonsai Model Families

Bonsai consists of two model families, both built from the **Qwen3** dense decoder-only architecture (GQA, SwiGLU MLP, RoPE, RMSNorm) and available at three scales: **8B**, **4B**, and **1.7B** parameters.

| Family | Bit Width | Weight Values | Footprint (8B) | Whitepaper |
|---|---|---|---|---|
| **Bonsai** (1-bit) | 1.125 bits/weight | {-1, +1} (sign only) | 1.15 GB (GGUF) / 1.28 GB (MLX) | [1-bit Bonsai 8B](../1-bit-bonsai-8b-whitepaper.pdf) |
| **Ternary-Bonsai** (1.58-bit) | ~1.71 bits/weight | {-1, 0, +1} | ~1.75 GB | [Ternary-Bonsai 8B](../ternary-bonsai-8b-whitepaper.pdf) |

*(1-bit whitepaper, Table 1; Ternary whitepaper, Table 1)*

In the demo repo, you select the family with the `BONSAI_FAMILY` environment variable (`bonsai` or `ternary`) and the scale with `BONSAI_MODEL` (`8B`, `4B`, or `1.7B`). See the [README](../README.md#environment-variables) for details.

---

## 3. Weight Formats and Quantization Schemes

### Q1_0_g128 (1-bit Bonsai)

Each weight is stored as a single sign bit in {0, 1}. Every group of 128 weights shares one FP16 scale factor. At inference time, the weight is reconstructed as:

```
w_i = s_g * (2 * b_i - 1),    b_i in {0, 1}
```

where `s_g` is the shared FP16 scale for group `g`. The effective storage cost is:

```
b_eff = 1 + 16/128 = 1.125 bits/weight
```

This yields **~14.2x compression** relative to FP16 (16 / 1.125). In the demo repo this format is packaged as a **GGUF** file and used by all llama.cpp backends (CUDA, Metal, Vulkan, ROCm, CPU). See [`bin/`](../README.md#folder-structure) for the pre-built binaries.

*(1-bit whitepaper, Section 4.1 "Deployable 1-bit Format: Q1_0_g128")*

#### MLX 1-bit g128 Variant

Apple's MLX framework requires both a scale and a bias per group. The 1-bit weights are packed by setting:

```
s_mlx = 2 * s_g
b_mlx = -s_g
```

This reconstructs `-s_g` when `b_i = 0` and `+s_g` when `b_i = 1`, but at a slightly higher effective cost of **1.25 bits/weight** due to storing two FP16 values per group.

*(1-bit whitepaper, Section 4.1 "MLX 1-bit g128")*

### Ternary g128 (Ternary-Bonsai)

Each weight takes a value from {-1, 0, +1}, with one shared FP16 scale per group of 128 weights:

```
w_i = s_g * t_i,    t_i in {-1, 0, +1}
```

Ternary code values carry log2(3) ~= 1.585 bits of information per weight. With the per-group scale overhead:

```
b_eff ~= 1.585 + 16/128 = 1.71 bits/weight
```

This yields **~9.4x compression** relative to FP16. The additional zero state makes ternary weights more expressive than binary, leading to better quality at a modest size increase. Since MLX does not yet provide native ternary kernels, deployment currently uses **2-bit MLX kernels** (Q2_0).

*(Ternary whitepaper, Section 2.1 "Ternary Weight Format")*

### Which Format Corresponds to What in the Repo

| Repo Concept | Whitepaper Format | Where You'll See It |
|---|---|---|
| `BONSAI_FAMILY=bonsai` + GGUF model | Q1_0_g128 | `models/gguf/` files, all `run_llama.*` and `start_llama_server.*` scripts |
| `BONSAI_FAMILY=bonsai` + MLX model | MLX 1-bit g128 | `models/Bonsai-*-mlx/` dirs, `run_mlx.sh`, `start_mlx_server.sh` |
| `BONSAI_FAMILY=ternary` + GGUF model | Q2_0 (ternary packed into 2 bits) | `models/gguf/` files with ternary prefix |
| `BONSAI_FAMILY=ternary` + MLX model | MLX 2-bit | `models/Ternary-Bonsai-*-mlx-2bit/` dirs |

---

## 4. The Pareto Frontier and Intelligence Density

Both whitepapers evaluate Bonsai models against 20 leading instruct models (0.6B--9B scale) across six benchmark categories: knowledge (MMLU-Redux), reasoning (MuSR), math (GSM8K), coding (HumanEval+), instruction following (IFEval), and tool calling (BFCLv3).

### Shifting the Pareto Frontier

On a scatter plot of **benchmark score vs. model size** (GB, log scale), the conventional Pareto frontier is defined by Qwen 3 0.6B/1.7B/4B/8B and Ministral 3 3B. The Bonsai models shift this frontier dramatically to the left:

| Model | Size | Avg. Score (6 benchmarks) |
|---|---|---|
| Qwen 3 8B (FP16) | 16.38 GB | 79.3 |
| **Ternary-Bonsai 8B** | **1.75 GB** | **75.5** |
| **1-bit Bonsai 8B** | **1.15 GB** | **70.5** |

Ternary-Bonsai 8B retains >95% of the full-precision model's quality at ~1/9 the memory. 1-bit Bonsai 8B retains ~89% at ~1/14 the memory.

*(1-bit whitepaper, Section 1 "The Pareto Frontier"; Section 5 Table 5; Ternary whitepaper, Section 1; Section 3 Table 6)*

### Intelligence Density

Raw average benchmark score does not reflect the nonlinear difficulty of improvement at higher scores. The whitepapers define:

```
P_e = 1 - (average_benchmark_score / 100)     # probability of error

Intelligence = -log(P_e)

Intelligence Density (D) = -log(P_e) / N       # per GB
```

This is analogous to error exponents in information theory. Under this metric, Bonsai models are extreme outliers --- delivering far more intelligence per GB than any conventional model:

| Model | Density (1/GB) | Size | Avg. Score |
|---|---|---|---|
| 1-bit Bonsai 1.7B | 2.832 | 0.24 GB | 49.6 |
| Ternary-Bonsai 1.7B | 2.389 | 0.37 GB | 58.5 |
| 1-bit Bonsai 4B | 1.744 | 0.57 GB | 62.7 |
| Ternary-Bonsai 4B | 1.426 | 0.86 GB | 70.7 |
| 1-bit Bonsai 8B | 1.060 | 1.15 GB | 70.5 |
| Ternary-Bonsai 8B | 0.803 | 1.75 GB | 75.5 |
| Qwen 3 8B (best conventional 8B) | 0.096 | 16.38 GB | 79.3 |

1-bit Bonsai 8B achieves **10.2x** the intelligence density of the closest conventional model in its weight class.

*(1-bit whitepaper, Section 5.1 "Intelligence Density" and Table 6; Ternary whitepaper, Section 3.1 and Table 7)*

See the [community-benchmarks/](../community-benchmarks/) directory for hardware-specific performance results contributed by users.

---

## 5. Cross-Platform Throughput

Because 1-bit models move ~14x less data from memory per decoding step, **token generation** is dramatically faster. Prompt processing (compute-bound, tokens processed in parallel) sees only modest gains (~1.0--1.1x).

### 1-bit Bonsai 8B Throughput (tg128 / pp512)

| Platform | Backend | Size | TG (tok/s) | FP16 TG (tok/s) | Speedup |
|---|---|---|---|---|---|
| RTX 4090 | llama.cpp CUDA | 1.15 GB | 368 | 59 | 6.2x |
| RTX L40S | llama.cpp CUDA | 1.15 GB | 327 | 52 | 6.3x |
| M4 Pro 48 GB | MLX (Python) | 1.28 GB | 131 | 16 | 8.4x |
| M4 Pro 48 GB | llama.cpp Metal | 1.15 GB | 85 | 16 | 5.4x |
| iPhone 17 Pro Max | MLX Swift | 1.28 GB | 44 | 14 (4-bit) | 3.2x |
| Samsung S25 Ultra | llama.cpp OpenCL | 1.15 GB | 19.6 | -- | -- |

*(1-bit whitepaper, Section 4.3 Table 3)*

### Ternary-Bonsai 8B Throughput (MLX 2-bit deployment)

| Platform | Backend | TG (tok/s) | FP16 TG (tok/s) | Speedup |
|---|---|---|---|---|
| M4 Pro 48 GB | MLX (Python) | 83 | 16 | 5.2x |
| iPhone 17 Pro Max | MLX Swift | 27 | 14 (4-bit) | 1.9x |

*(Ternary whitepaper, Section 2.3 Tables 3--4)*

In the demo repo, these backends correspond to the scripts in `scripts/` and the pre-built binaries in `bin/`. The [README > Running the Model](../README.md#running-the-model) section maps each script to its backend.

---

## 6. Energy Efficiency

Higher instantaneous power draw (from inline dequantization) is more than offset by faster generation, resulting in **significantly lower energy per output token**.

### 1-bit Bonsai 8B Energy

| Platform | 1-bit (mWh/tok) | FP16 (mWh/tok) | Advantage |
|---|---|---|---|
| Mac M4 Pro (MLX) | 0.074 | 0.415 | 5.6x |
| Mac M4 Pro (Metal) | 0.091 | 0.471 | 5.1x |
| RTX 4090 (CUDA) | 0.276 | 1.134 | 4.1x |
| iPhone 17 Pro Max | ~0.068 | ~0.143 (4-bit) | 2.1x vs 4-bit |

*(1-bit whitepaper, Section 4.4 Table 4)*

### Ternary-Bonsai 8B Energy

| Platform | Ternary (mWh/tok) | FP16 (mWh/tok) | Advantage |
|---|---|---|---|
| Mac M4 Pro | 0.105 | 0.415 | 4.0x |

*(Ternary whitepaper, Section 2.4 Table 5)*

Energy per token is defined as `E_tg = P_tg / (3.6 * r_tg)` where `P` is inference power in watts and `r` is tokens per second.

*(1-bit whitepaper, Appendix D.3 "Energy Definitions")*

---

## 7. Backend Implementations

Q1_0_g128 is **not** natively supported by upstream llama.cpp or MLX; PrismML built custom kernels for each backend. This is why the demo repo uses the [PrismML fork of llama.cpp](https://github.com/PrismML-Eng/llama.cpp) and the [PrismML fork of MLX](https://github.com/PrismML-Eng/mlx).

| Backend | Implementation | Repo Script |
|---|---|---|
| **llama.cpp CUDA** | Custom CUDA kernels for 1-bit matrix-vector and matrix-matrix multiply with inline sign-bit unpacking | `scripts/build_cuda_linux.sh`, `scripts/build_cuda_windows.ps1` |
| **llama.cpp Metal** | Custom Metal compute shaders for single-token decoding and batched prompt processing | `scripts/build_mac.sh` |
| **MLX (macOS)** | Custom Metal GPU kernels in a PrismML MLX fork (`prism` branch) | `scripts/run_mlx.sh`, `scripts/start_mlx_server.sh` |
| **mlx-swift (iOS)** | Separate PrismML fork of mlx-swift with independent 1-bit Metal kernels | (mobile deployment, not in this demo repo) |
| **CPU (generic)** | Sign-bit unpacking in generic C/C++ | `scripts/build_cpu_linux.sh`, `bin/cpu/` |
| **Vulkan** | Community-contributed shader (upstream merged) | Covered by pre-built binaries in `bin/vulkan/` |
| **ROCm / HIP** | Available in the PrismML fork | `bin/rocm/`, `bin/hip/` |

For the 1-bit (Q1_0) format, several backends have already been **merged upstream** into llama.cpp --- see the [README > Upstream Status](../README.md#upstream-status-for-1-bit-q1_0) tables. Ternary (Q2_0) backends remain in the PrismML fork for now.

### Why Pre-built Binaries Exist

Because custom kernels are required, the demo repo ships pre-built binaries from the [PrismML llama.cpp release](https://github.com/PrismML-Eng/llama.cpp/releases/tag/prism-b8846-d104cf1) covering 15+ platform/backend combinations. `setup.sh` downloads them automatically; alternatively, you can build from source with the `scripts/build_*.sh` scripts.

*(1-bit whitepaper, Appendix A "Achieving 1-bit Inference Acceleration")*

---

## 8. Benchmark Methodology

Both whitepapers use the same evaluation framework and controls to ensure fair, reproducible comparisons.

### Infrastructure

- **Framework:** EvalScope v1.4.2 + vLLM 0.15.1 backend
- **Hardware:** NVIDIA H100 80 GB (8x H100 node)
- **Determinism:** Flash Attention 2 + `VLLM_BATCH_INVARIANT=1` + seed 42
- **Decoding:** Greedy (temp=0.0, top_p=1.0), thinking mode disabled. Exception: GPQA Diamond uses 10-sample mean (temp=0.6, top_p=0.95).

### Benchmark Suite (10 benchmarks, 6 categories)

| Category | Benchmarks |
|---|---|
| Knowledge | MMLU-Redux (57 subjects), GPQA Diamond (198 questions) |
| Reasoning | MuSR (756 multistep soft reasoning questions) |
| Math | GSM8K (1,319 problems), MATH-500 (500 problems) |
| Coding | HumanEval+ (164 problems), MBPP+ (378 problems) |
| Instruction Following | IFEval (541 prompts), IFBench |
| Tool Calling | BFCLv3 (13 single-turn subsets) |

### Scoring

- **IFEval / IFBench:** Rule-based constraint checking only (no LLM judge). Metric: strict OLLM average.
- **BFCLv3:** AST matching + execution verification.
- **Code (HumanEval+ / MBPP+):** Sandbox execution in Docker (`python:3.11-slim`).
- **Knowledge / Math:** Rule-based extraction with LLM recall fallback (Gemini 2.5 Flash Lite, temp=0.0) only when rule-based parsing fails.

### Fair Comparison Guarantees

All models use: same infrastructure, same generation parameters, same benchmark versions and dataset revisions, same scoring pipeline and judge model, deterministic execution, and no per-model prompt engineering.

*(1-bit whitepaper, Appendix B "Benchmark Evaluation Methodology"; Ternary whitepaper references the same methodology)*

---

## 9. Limitations and Roadmap

- **Software-only acceleration:** Results are on general-purpose hardware via kernel optimization, not purpose-built 1-bit silicon. Native hardware support would likely improve results further.
- **Mobile energy estimates:** iPhone energy figures are estimated from battery drain, not hardware-metered.
- **MLX ternary support:** MLX does not yet provide native ternary (1.58-bit) kernels; Ternary-Bonsai currently uses 2-bit MLX kernels, so deployed footprint exceeds the theoretical minimum.
- **Architecture-agnostic:** The Bonsai methodology is not tied to Qwen3; future releases will extend to newer model backbones, hybrid architectures, and diffusion models.
- **Additional bit widths:** Near-term roadmap includes Bonsai variants at different bit widths and further efficiency mechanisms.

*(1-bit whitepaper, Section 7 "Limitations and Roadmap"; Ternary whitepaper, Section 2.2 re: MLX deployment gap)*

---

## 10. Mapping the Whitepapers to the Demo Repo

This section connects each major whitepaper concept to its concrete counterpart in this repository.

| Whitepaper Concept | Repo Artifact | Notes |
|---|---|---|
| Q1_0_g128 format | `models/gguf/` GGUF files (1-bit family) | Downloaded by `scripts/download_models.sh` with `BONSAI_FAMILY=bonsai` |
| Q2_0 / Ternary g128 format | `models/gguf/` GGUF files (ternary family) | Downloaded with `BONSAI_FAMILY=ternary` |
| MLX 1-bit g128 | `models/Bonsai-*-mlx/` directories | macOS only; downloaded by setup |
| MLX 2-bit (ternary deployment) | `models/Ternary-Bonsai-*-mlx-2bit/` directories | macOS only |
| PrismML llama.cpp fork | `bin/` pre-built binaries; `scripts/build_*.sh` scripts | Custom CUDA, Metal, and CPU kernels for Q1_0 |
| PrismML MLX fork | `mlx/` directory (cloned at setup) | Custom Metal kernels for 1-bit; `prism` branch |
| Cross-platform backends (CUDA, Metal, Vulkan, ROCm, CPU) | `bin/cuda/`, `bin/mac/`, `bin/vulkan/`, `bin/rocm/`, `bin/cpu/` | See [README > Pre-built Binary Downloads](../README.md#llamacpp-pre-built-binary-downloads) |
| Token generation speedup | Verified via `scripts/run_llama.sh`, `scripts/run_mlx.sh` | The scripts auto-detect backend and pass `-c 0` for auto-fit KV cache |
| Benchmark evaluation | `community-benchmarks/` | Community-contributed results on real hardware |
| Model families & sizes | `BONSAI_FAMILY` and `BONSAI_MODEL` env vars | See [README > Environment variables](../README.md#environment-variables) |
| End-to-end setup | `setup.sh` / `setup.ps1` | Installs deps, downloads models + binaries, builds MLX fork |
| Chat interface | `scripts/start_llama_server.sh`, `scripts/start_openwebui.sh` | llama-server on port 8080; Open WebUI on port 9090 |

---

## Further Reading

- **Model Families and Quantization Formats:** [README > Models](../README.md#models)
- **Hardware Backends and Build Instructions:** [README > Building from Source](../README.md#building-from-source)
- **Community Benchmarks:** [community-benchmarks/](../community-benchmarks/)
- **CI and Smoke Testing:** [.github/CI.md](../.github/CI.md)
- **GitHub Runners:** [.github/github-runners.md](../.github/github-runners.md)
