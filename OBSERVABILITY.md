# Observability

The Prism UI adds an `/observability` route that reads local recording artifacts
and MLflow traces. It separates three kinds of evidence:

- **Native inference exchanges:** exact local HTTP request and response bytes.
- **Browser/tool exchanges:** proxied MCP calls with model-emitted tool-call IDs
  linked to subsequent tool-result messages when present.
- **Instrumented replay:** a new, separate llama.cpp execution of a recorded text
  prompt, capped at 32 decode steps and selected layers by default.

Replay vectors are not the original production request activations and are not a
causal explanation of an answer. They are measurements from a later instrumented
execution of the same rendered context.

## Activation Vectors

When replay succeeds, the UI can request one full residual-stream vector at a time
through `/api/observability/activation-vector`. The server verifies that the vector
path is inside configured recording storage, that its byte length matches the
manifest, and that its SHA-256 hash matches before returning values.

## Model Evidence

Attach `--release-manifest` when starting `recording_ui.py` to show checkpoint
provenance beside traces. A loaded model is only marked verified when the current
server path matches a previously hash-verified manifest entry.

## Limits

- A trace records one HTTP exchange, not a full agent run.
- Sequence edges mean recorded order, not proof of causality.
- Reasoning text is generated model output, not measured hidden state.
- Missing token, cost, or activation data means unavailable, not zero.
