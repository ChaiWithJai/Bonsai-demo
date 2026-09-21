# Bonsai Workspace experiment

The Workspace tab adds an incremental UI editing workflow to this fork.
It reuses the existing branding, inference server, recording proxy, and
observability screens. The separate desktop prototype is frozen at
`ChaiWithJai/bonsai-generative-ui@a69afd8290de71a18755f934516a0ed9f649afe6`.

## Model, task, and harness

The first model is Bonsai 2 27B with the previously verified Prism runtime and
PQ2_0 checkpoint. The service stays running across requests. A transport adapter
connects to its recording proxy and never starts or restarts inference.

The first task starts with the existing cached source explorer and its 14
records. Turn one adds runtime drilldown under parameter size groups. Turn two
filters existing saved notes to the selected record while preserving turn one
and note persistence. Missing values, zero values, and source identities must
survive both turns.

The harness lets the model read files, apply exact text edits, build, preview,
and check the browser. Each edit names its base revision. Build and browser
failures return to a bounded repair loop. The next turn starts from the saved
project. It does not ask the model to recreate the application.

## Current implementation status

The native `#/workspace` tab now uses the fork's branding and recording service.
It opens the existing explorer, saves revisions, shows source and preview panes,
and links the current attempt to MLflow. The worker runs on the server, so a
browser reload reads saved events without restarting generation.

* `workspace_store.py` stores immutable revisions and ordered attempt events.
  It rejects stale patches and cancelled attempts. Each patch and its event
  commit together.
* `workspace_provider.py` streams native tool calls through the recording proxy.
  It applies the earlier harness's explicit `enable_thinking: false` request
  setting and enables prompt cache reuse. Each model call has a 120-second limit
  and a 4,096-token output budget by default.
* `workspace_worker.py` preserves prior completed conversation context. It allows
  eight model calls, two compiler/browser repairs, a ten-minute attempt, and fixed read, patch,
  build, preview, and browser-check tools. An exclusive store lock prevents a
  second worker from interrupting an active attempt. A repeated unmatched patch fragment on the same revision stops on its second occurrence and records a `loop.detected` event, span, and artifact. This deterministic guard is separate from the optional MLflow tool-efficiency judge.
* `workspace_tools.py` compiles only the saved Svelte component with the authored
  compiler. It never runs a generated build configuration. Each workspace gets
  a separate loopback preview origin and a persistent source-note store.
* `workspace-tools/check.mjs` checks source identities, values and links, runtime
  drilldown, note filtering, note persistence, mobile overflow, and browser errors.
  Automated notes are labeled `workspace-automated-check`.

The first live W1 attempt with provider contract v2 passed after Bonsai repaired
an event-handler syntax error. It took 87.97 seconds with one compiler repair.
Run `b19ec999a7ac4733857707a083327e63` preserves the source, patch, failed build,
repair, browser assertions, screenshots, and complete attempt trace. The earlier
v1 attempt `2486ca6033f54889b02c9de565203048` timed out during reasoning output
before applying a patch and remains recorded. This is development evidence.

The repository's 146 Python tests passed with `PYTHONPATH=scripts` and a resolved
macOS temporary directory. The Workspace component passed Svelte checking and
its production build. The second live turn has failed and remains an open acceptance gate. A later W1 continuation passed after native context preflight and an explicit context checkpoint. The September 21 loop audit distinguishes reasoning timeouts, context overflow, and repeated rejected patches. See [the diagnosis](research/loop-diagnosis-20260921/REPORT.md).

The native recorder retains one trace per HTTP exchange. Workspace attempt
traces link those exchange IDs explicitly. Distributed trace parentage is not
claimed. Automatic activation replay is skipped for Workspace sessions so a
second GPU workload is not started between tool calls.

## Run locally

Install the fixed tool dependencies with `npm ci --prefix scripts/workspace-tools`.
Build the branded UI using the existing source and dependencies:

```sh
python scripts/build_prism_ui.py --source /path/to/llama.cpp/tools/ui
```

Start the existing recording service with its usual arguments plus
`--workspace-dir /path/to/persistent/workspace-store`. Supply a release manifest
that matches the loaded model. Workspace calls that recorder's own loopback
completion route. It never starts or restarts the inference process.

The experiment launcher currently uses the shared lab GPU reservation. The
Mac model remains loaded across both model calls and user turns. The GB10 lane
is unchanged. Build saved revision opens an existing project without inference.

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
PYTHONPATH=scripts python -m unittest discover -s tests -p 'test_workspace_*.py' -v
PYTHONPATH=scripts python -m unittest discover -s tests -p test_recording_ui.py -v
```

## Explicit sampling experiments

`--workspace-profile legacy-greedy` preserves the historical temperature-zero
configuration. `--workspace-profile bonsai2-instruct` uses the pinned model
card's non-thinking sampling settings. `--workspace-profile bonsai2-medium`
uses its thinking sampling settings with medium effort. `--workspace-seed`
records a chosen seed. Medium effort and a numeric thinking-token cap are
different controls. Verify the loaded server's template and effective limits
before a thinking trial. No sampled profile has been promoted by default.

`research/loop-diagnosis-20260921/compare_profiles.py` runs sequential development
trials from copies of the saved W1 project, including its prior conversation.
It preserves the original workspace and logs every trial. This dated experiment
script requires the documented local pilot paths and a warm, idle model. It is
not the application launcher or a benchmark of latency.

## Remaining product scope

The generated project still uses the cached 14-record fixture. The native Data
panel now accepts desktop files, preserves source bytes and locations, records
corrections separately, and exports reviewed examples with MLflow evidence.
The intake and review modules are reused from the frozen prototype. Uploaded
media is stored with pending extraction status.

Connecting those uploaded records to classification, Semiotic views, generated
projects, and multimodal extraction remains open. The native Workspace is not
yet a complete replacement for the prototype workflow. The [sampling comparison
and data checkpoint](research/loop-diagnosis-20260921/COMPARISON.md) records the
failed W2 trials, successful source-review checks, and next intervention.
