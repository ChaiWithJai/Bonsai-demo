# Harness choices for desktop data interfaces

The next harness should produce a recorded data interpretation and visualization specification before rendering an interface. This is an engineering hypothesis informed by the current failures, not a measured improvement yet.

## Two complementary approaches

Dex Horthy's [Advanced Context Engineering for Coding Agents](https://www.humanlayer.dev/blog/advanced-context-engineering), published August 29, 2025, emphasizes deliberate context management. Research, plans and implementation are separate artifacts. Review of the research and plan can catch wrong assumptions before they become code. His examples also describe failures where research missed dependencies. For this project, the corresponding artifacts are the source inventory, extracted records, schema decisions and visualization plan. A short plan must keep links to its evidence. Compaction must not erase uncertainty or provenance.

Vivek Trivedy's [Improving Deep Agents with harness engineering](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering), published February 17, 2026, emphasizes changes informed by execution traces. The article reports holding the model fixed while changing the surrounding system. It describes explicit verification, environment context, and detecting repeated edits that do not resolve a failure. For this project, the corresponding controls are stage validation, source-aware interaction tests and bounded repair with the actual error attached. The article's benchmark results do not predict Bonsai performance.

Both approaches improve the information and controls around a model. Their emphasis differs: Horthy focuses on what enters context and where people review decisions; Trivedy focuses on observed execution failures and the feedback loop. Neither source establishes that our current model can interpret every desktop media format.

## Decisions tied to our evidence

The following run metrics were read again from the local MLflow server on September 21, 2026. The original outputs and scores remain unchanged.

| Observed failure | Evidence | Harness change to evaluate |
| --- | --- | --- |
| Generation exhausted its output allowance before completing a component | [Baseline run](http://127.0.0.1:5210/#/experiments/27/runs/ba2bb2de734d4019b09cefc800bc8210): 6,500 completion tokens, finish reason `length`, build failed | Ask for a bounded visualization specification; use maintained rendering components |
| Compilation succeeded but no record view appeared | [First repair](http://127.0.0.1:5210/#/experiments/27/runs/16511f206030472ab1fc734ed2dfbd87): build passed, browser execution failed while waiting for records | Validate rendered behavior against the data task before labeling the attempt successful |
| Common checks missed absent group controls | [Final model output](http://127.0.0.1:5210/#/experiments/27/runs/f9e75e496f3f49338c104a9c03ccc796): eight common checks passed; the [separate group supplement failed](reviewed-cache-provenance.json) | Derive category-specific checks from the selected visualization and actual source fields |

The final output adapted a Codex-authored reference. A separate Codex correction fixed the group expression. Those interventions cannot be counted as unaided model success.

## Implementation sequence and acceptance

1. Preserve uploaded bytes, source hashes and extraction locations. Tables and text now have this path. Media registration remains explicitly pending extraction.
2. Extract media through verified adapters. Record which model or library performed OCR or transcription. An audio transcript passed to a text model is not native audio reasoning.
3. Have Bonsai propose a typed schema and classifications using bounded source context. Keep the proposal, validation errors and user corrections separately.
4. Have Bonsai select a versioned visualization specification with source field references. Verify Semiotic's actual integration contract before choosing the adapter. The current documentation navigation alone is insufficient evidence for a schema or Svelte compatibility claim.
5. Render the specification with maintained components. Test selection, filtering, missing values, source links and annotations against the supplied data.
6. Preserve requests, responses, stage results and correction authors in MLflow. Export examples for a training loop with source provenance and review status. Do not turn provisional Codex review into human labels.

A successful stage does not establish success of subsequent stages. The desktop workflow is complete only when the file-to-interface examples execute through the model, survive interaction checks and retain their evidence.
