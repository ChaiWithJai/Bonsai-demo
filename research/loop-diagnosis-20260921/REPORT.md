# Bonsai Workspace loop diagnosis

Observed September 21, 2026. New UI generations are paused. The saved W1 project remains at revision `7c89f55427c2fd69cb5d7714cf64cdcdd71fab93fa806c46cab3037ed26008ee`. W2 has not passed.

## Finding

The latest failure is a repeated failed edit, with no emitted reasoning. It is not evidence that a larger reasoning budget will fix the task. Three patches carried the same incorrect source fragment, whose SHA256 is `9de1b749f5ae6ed2e8ca6dd7dd89ca50fead1ac231be21004f1c8c2e880c9075`. Its closing article tag has four tabs where the current source has three. All three patches were rejected atomically. No project revision changed. A fourth patch generation timed out after the per-call wall-clock limit. The whole attempt lasted 258.19 seconds.

The five recorded generation streams each contain zero reasoning-content characters. The final interrupted stream contains 870 tool-argument characters. It should not be labeled an infinite token loop from these observations alone. The demonstrated loop is repeated unsuccessful action selection.

The harness amplified the failure. Exact-match patch rejection did not consume its compiler/browser repair budget, so the summary misleadingly reports zero repairs despite three failed edit attempts. Its diagnostic returned the proposed fragment, rather than nearby actual source. The model did not re-read after the failures. A call limit eventually bounds retries, but does not identify stalled progress early.

## MLflow assessment

MLflow 3.16.0 includes the built-in ToolCallEfficiency rubric. It is an LLM judge that must be invoked, not an automatic detector enabled by logging. This trace initially had no assessments.

We executed the unchanged built-in prompt through MLflow's judge invocation with explicit local inference parameters and no configured inference retries. This is not the default ToolCallEfficiency wrapper. The local Bonsai judge returned `no` for efficiency. Its result is attached to the original trace as `tool_call_efficiency_local`.

The judge's rationale overstates one detail: the full second and third tool arguments were not identical. An unrelated edit changed. The failing fragment itself was identical across all three rejected patches, which is confirmed by hashes independently of the judge. This is an uncalibrated same-model assessment, not a human label or independent quality estimate. Preserve that disagreement when reviewing the result.

[Original run](http://127.0.0.1:5210/#/experiments/31/runs/95469b2f5d1649478f9ca0dba84f3050). Trace: `tr-a38715d1c5e7f9ce284202dc0cb8a09a`.

## Configuration and source alignment

| Dimension | Current failed UI attempt | Published guidance or evaluation | Implication |
| --- | --- | --- | --- |
| Thinking | Explicitly disabled in request; zero emitted reasoning | Paper evaluates thinking mode. Card supports instruct mode too | Do not transfer thinking benchmark results to this run |
| Sampling | Temperature 0, seed 42; other sampling values omitted | Card instruct profile: temperature .7, top-p .80, top-k 20, min-p 0, presence penalty 1.5, repetition penalty 1 | Test a complete explicit profile rather than relying on inherited defaults |
| Thinking profile | Not exercised in latest run | Temperature 1, top-p .95, top-k 20, min-p 0, no presence penalty, repetition penalty 1 | Compare separately from the instruct profile |
| Effort | No request effort | Card and paper specify medium or xhigh; low does not shorten thinking | A low label is not a reliable latency control |
| Context | Actual server slot 16,384, reserving 4,096 output tokens | Paper agent evaluation uses 262,144 context and 80,000 output tokens per turn | Our interactive budget is a different operating point |
| Tools | Native tool messages, exact source replacement, Svelte build/browser checks | Paper BFCL uses prompt-based calls; SWE uses mini-swe-agent | Task and harness differences are material |
| Runtime | Prism b10709-9a9394a, PQ2, local Metal | Paper benchmarks use vLLM/H100 | No runtime-equivalent quality claim |

The pinned card and local paper also describe different benchmark-suite revisions (14 versus 20 benchmarks). Preserve both revisions. Do not merge their averages.

Sources: [pinned model card](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/blob/6ed5e12bf84b7a63069882c91dd9e9218647d17b/README.md), [Bonsai 2 paper in fork](https://github.com/ChaiWithJai/Bonsai-demo/blob/f30ad2748fdb689bcd9c64a5fb190f72412036bf/bonsai-2-27b-whitepaper.pdf), [MLflow ToolCallEfficiency](https://www.mlflow.org/docs/latest/genai/eval-monitor/scorers/llm-judge/tool-call/efficiency/).

Local paper SHA256: `aea10331ede3b34c34c21d1a45b80fd0fd6e231b3e8db7bd6346e20fcb8402c4`. Model SHA256: `3907dc1658db1f78a9826bf8d5bcb8dc65db0d466388937af57f2294fae62ec1`.

A [firsthand community report](https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-gguf/discussions/18) describes exhausting 32K reasoning tokens on a mathematical coding task even with the recommended thinking sampling. It uses a different runtime, hardware, context, and task. This motivates a failure test; it does not establish our failure's cause or prevalence.

## Separate failure modes

1. Initial pilot: request omitted explicit thinking-off and reasoning consumed the response window. Server configuration alone did not produce the intended request behavior. A timeout is not by itself proof of repetition.
2. Earlier W2: browser failure followed by a syntax-breaking repair and exhausted call budget.
3. W1 continuation: accumulated history exceeded the real 16K slot. Native token preflight and deterministic context checkpoint subsequently allowed W1 verification to pass. This is distinct from repetition.
4. Latest W2: repeated identical failing source fragment, unchanged revision, followed by a generation timeout. Explicit thinking-off did not prevent this action loop.

## Next controlled task

Freeze the current W1 revision, W2 request, source records and browser acceptance checks. Do not replace the project with a blank starter. Stop a trial when the same failed patch fragment recurs on the same revision. Save that event and exact diagnostics in its MLflow trace. Supply nearby actual source for repair; do not silently apply fuzzy patches.

First compare the current greedy configuration with the full documented instruct profile while holding prompt, harness, context policy and task fixed. Next compare the documented medium-thinking profile with the documented instruct profile. Verify the actual template and effective token cap before inference. Do not call a numeric token cap 'medium effort'; they are different controls. Keep explicit wall-clock and output limits for every trial, and count timeouts as failures.

Then test improved source diagnostics as a separate harness change. Use at least three fixed seeds per sampled configuration for development screening, with order recorded. Measure browser acceptance, repeated failed fragment count, no-progress duration, valid patches, source reads after rejection, reasoning/output volume, latency and context checkpoints. These few development examples cannot estimate general model reliability.

No configuration change has been promoted and no new W2 generation has been launched during this audit. The one local judge invocation only assessed the saved trace. The current UI is http://127.0.0.1:5257/#/workspace; 5255 is the earlier pilot.
