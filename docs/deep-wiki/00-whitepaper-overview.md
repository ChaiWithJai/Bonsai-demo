# Whitepaper Overview

> **Status:** Stub — full deep-dive being created separately.
>
> **Last updated:** 2026-06-27

---

## Whitepapers

PrismML has published two whitepapers documenting the Bonsai model family:

| Paper | File | Model Family |
|-------|------|-------------|
| 1-bit Bonsai 8B | [`1-bit-bonsai-8b-whitepaper.pdf`](../../1-bit-bonsai-8b-whitepaper.pdf) | Bonsai (1-bit, {-1, +1} weights) |
| Ternary-Bonsai 8B | [`ternary-bonsai-8b-whitepaper.pdf`](../../ternary-bonsai-8b-whitepaper.pdf) | Ternary-Bonsai (1.58-bit, {-1, 0, +1} weights) |

Both papers describe native low-bit training methods that preserve reasoning
capability while achieving 9-14x compression of the model footprint.

---

## Key Concepts (Preview)

- **Intelligence Density:** Defined as −log(average error rate) / model size
  (GB). The core metric PrismML uses to compare efficiency across model
  families. 1-bit Bonsai 8B achieves 1.06/GB vs. 0.10/GB for Qwen3 8B.
- **Native 1-bit Training:** Unlike post-training quantization (GPTQ, AWQ),
  Bonsai models are trained with 1-bit weights from the start. Each weight is
  represented by its sign {-1, +1} with a shared FP16 group-wise scale factor.
- **End-to-End Low-Bit:** Embeddings, attention layers, MLP layers, and LM head
  are all 1-bit — no higher-precision escape hatches.
- **Ternary Extension:** Ternary-Bonsai adds a zero state {-1, 0, +1} for 1.58
  bits per weight, trading a modest size increase for stronger benchmark
  performance.

---

## Who Built This and Why

The theoretical and organizational backstory behind these whitepapers is
documented in the **[Founders & Proof Timeline](./01-founders-proof-timeline.md)**
section, which covers:

- **Babak Hassibi's compression-theory lineage** — from Optimal Brain Surgeon
  (1992-93) through three decades of neural network optimization at Caltech,
  providing the theoretical heritage for Bonsai's quantization approach.
- **The founding team's research backgrounds** — how RL/control theory (Lale),
  second-order optimization (Pooladzandi), and applied ML infrastructure
  (Sadri) converge in the Bonsai training pipeline.
- **Investor validation of the intelligence-density thesis** — Khosla Ventures
  and Cerberus Ventures (led by the founder of Google's TPU program) betting
  on intelligence per unit of energy and cost.

---

## Full Deep-Dive (Coming Soon)

A comprehensive whitepaper analysis — covering training methodology,
quantization mechanics, benchmark evaluation, and architectural decisions — is
being prepared as the "crown jewel" section of this deep wiki. It will appear
here when complete.
