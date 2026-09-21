# Bonsai Workspace experiment

The planned Workspace tab adds an incremental UI editing workflow to this fork.
It reuses the existing branding, inference server, recording proxy, and
observability screens. The separate desktop prototype is frozen at
`ChaiWithJai/bonsai-generative-ui@a69afd8290de71a18755f934516a0ed9f649afe6`.

## Model, task, and harness

The first model is Bonsai 2 27B with the previously verified Prism runtime and
PQ2_0 checkpoint. The service stays running across requests. A transport adapter
connects to its recording proxy and never starts or restarts inference.

The first task starts with the existing reviewed cache explorer and its 14
records. Turn one adds runtime drilldown under parameter size groups. Turn two
filters existing saved notes to the selected record while preserving turn one
and note persistence. Missing values, zero values, and source identities must
survive both turns.

The harness will let the model read files, apply exact text edits, build, preview,
and check the browser. Each edit names its base revision. Build and browser
failures return to a bounded repair loop. The next turn starts from the saved
project. It does not ask the model to recreate the application.

## Current implementation status

The Workspace tab and complete attempt worker are **not wired into the app yet**.
The first foundation includes:

* `scripts/workspace_store.py` saves immutable revisions and ordered attempt
  events in SQLite. It rejects stale edits, patches from cancelled attempts,
  dependency changes, and edits attributed to another workspace. A patch and
  its event commit in one transaction. Browser reconnect reads persisted events.
* `scripts/workspace_provider.py` streams content and native tool calls from an
  existing local recording proxy. It bounds output and elapsed time, interrupts
  a silent stream on cancellation, rejects incomplete completions, and retains
  the proxy trace ID. It does not retry requests automatically.
* Thirteen tests cover revision continuity, atomic rollback, restart recovery,
  transport limits, tool fragments, cancellation, and incomplete responses.
  Transport tests use a local HTTP fixture. They are not live model evidence.

On exclusive service startup, the future worker must call
`recover_interrupted()` once. Browser reconnect must never call it. The store
does not provide service ownership locking. That belongs in worker integration.

The future worker must preserve provider failures and link proxy exchange traces
to its own complete attempt trace. A proxy trace ID alone does not establish
distributed parentage or prove a complete successful attempt.

## Next acceptance gate

1. Reuse the authored starter and its pinned compiler and data contract.
2. Add a bounded worker with fixed tools, isolated previews, cancellation, and a
   complete MLflow attempt trace.
3. Add the native Svelte `#/workspace` route through `build_prism_ui.py`.
4. Verify both model turns against data and browser assertions. Reload between
   turns and prove that the second turn retains the first turn's changes.
5. Inspect desktop and mobile surfaces and retain the review evidence.

The research plan is revision 3 in MLflow experiment
`bonsai-v0-harness-research`, run `37fe164f40c546339c688b40af523203`.
Its SHA256 is
`75230b50dbc1ad332673f70e9a836bbf768a2810c46b72e452fe67cd59cc65b6`.
The plan preserves the earlier failure traces and compares harness structures
with Open SWE, Gemini CLI, and Agent Substrate. The broader experiment matrix
follows the two-turn acceptance gate.

Run the foundation checks with Python 3.11 or 3.12:

```sh
python -m unittest discover -s tests -p 'test_workspace_*.py' -v
python -m unittest discover -s tests -p test_recording_ui.py -v
```
