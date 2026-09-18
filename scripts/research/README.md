# Official Pelican inference research

Run on the GB10 with the existing private `.venv/bin/python`. The HF runner is offline-only: the exact pinned official snapshot must already be fully cached. It validates every tensor against the safetensors index, BF16 dtype, shard byte completeness and the 27,781,427,952 parameter count before loading. It checks the loaded parameter count again. No third-party Qwen quantization is accepted.

```
.venv/bin/python scripts/research/official_pelican.py \
  --model Qwen/Qwen3.8-27B \
  --output /home/chaiwithjai/bonsai-workspace/research-records/NEW_32_HEX_ID
```

The prompt is `Generate an SVG of a pelican riding a bicycle`. Default output budget and activation capture bound are 4096 each; both can be set up to 8192. Layers 0, 31 and 63 are captured throughout generation, including the final prefill position. Full float32 residual vectors, statistics and exact token IDs are retained; tensors are checked for finite values. This is the original instrumented generation, not a replay.

Uniform research sampling is temperature 0.3, top-p 0.95, top-k 20, min-p 0, repetition penalty 1, seed 42, thinking disabled. This is not the white paper's evaluation protocol. A fresh explicit Transformers GenerationConfig prevents inheriting additional penalties or forced tokens; official BOS/EOS/pad IDs remain in use. `effective-generation-config.json` records every effective setting. Instrumentation synchronization affects timing.

## Token alignment

HF forward call 0 processes the prompt and predicts generated token 0. HF forward call N > 0 consumes generated token N-1 and predicts generated token N. The UI decode step is N-1 (the consumed token), while the prefill vector is separately retained. Generation normally stops after predicting the final token; that final token is therefore not consumed by another HF forward call. N generated tokens normally have N forward calls: one prefill and N-1 decode calls.

The native Bonsai capture consumes generated token N at decode step N and records the residuals that predict the next token. It performs that decode for every non-EOG token included in its output. Its token 0 is obtained from unrecorded prefill. The two capture manifests align on consumed generated token index, but have different terminal coverage and prefill coverage. Do not compare raw vector counts as a quality score.

Neuron dimensions are not assumed semantically aligned across checkpoints. These residual activations reveal measured values, not a causal explanation of an answer or changes to model weights. Native Bonsai uses its official packed ternary PQ2_0 release; Qwen uses its official BF16 release. Runtime/format differences preclude treating this as a controlled precision comparison.

## Official auxiliary MTP weights

The official checkpoint contains 1,199 tensors and 27,781,427,952 parameters. Standard Transformers Qwen3_5 autoregressive generation loads 1,184 tensors totaling 27,356,728,560 parameters. The exact difference is the 15 auxiliary `mtp.*` tensors (424,699,392 parameters); the installed official model class explicitly lists `^mtp.*` as ignored unexpected weights. Multi-token prediction is not enabled in this evaluation. Vision parameters remain loaded, but the prompt is text-only.

The runner audits the meta model against every official tensor name and shape before GPU loading. Only the exact enumerated MTP names and shapes may be excluded; missing or mismatched functional weights fail. The loader report is saved and checked, and the loaded parameter count must equal the audited functional count. Both checkpoint and loaded counts are recorded separately.

Loading sets the supported Transformers `HF_DEACTIVATE_ASYNC_LOAD=1` option to avoid queuing weight-copy futures on GB10 unified memory. This changes loading behavior, not checkpoint precision or inference math.

Before inference, run `verify_official_snapshot.py --repo REPO --revision FULL_COMMIT --snapshot EXISTING_DIRECTORY --output MANIFEST.json`. This fetches publisher metadata only and verifies every present file against its Git blob or LFS SHA256 digest, requiring all weight shards, tokenizer and configuration. It never downloads another copy of the weights. Preserve the manifest with the evaluation records.

## Sampler-order audit

The final native capture uses temperature → top-k → top-p → min-p → categorical sampling, matching the Transformers warper ordering. Initial Bonsai research runs used top-k/top-p before temperature and remain separately retained; do not mix them into the final aligned-order comparison. Equal seeds still do not imply identical draws across runtime implementations. Corrected native captures record measured prefill-plus-decode time, excluding model loading, and archive the exact capture source and small executable with SHA256 checks. HF captures archive the runner and helpers; the earlier Qwen3.6 record instead has an explicitly post-run installed-source audit.

## Execution environment and evidence

These are experiment runners for the existing GB10 environment, not a self-contained benchmark installer. The bounded GSM8K/IFEval scripts expect the pinned data, evaluator sources, model identity files, and isolated dependencies retained under `docs/research-20260918` and `.cache`; those local evidence directories are not published with this fork. Their protocol JSON and MLflow artifacts record exact revisions and deviations. The Hugging Face runner was measured with PyTorch 2.14.0+cu130 and Transformers 5.5.4. The native build requires the matching Prism llama.cpp headers/libraries identified by the build script. Configure paths and tracking destinations before using another machine. None of this is required on the MacBook to visit the running demo URL.

MLflow spans are imported after generation. Their short span durations measure artifact logging, not model generation; use the separately recorded instrumented inference duration. Original live activation evidence remains linked by request hash and exact model identity. `summarize_pelican.py` audits the fixed final run IDs and renders invalid SVG as an explicit evaluation failure, preserving original text instead of repairing or selecting another sample.
