# Harness choices for desktop data interfaces

The harness now records a data interpretation and visualization specification before rendering an interface. Development runs show that explicit source contracts can avoid a repair, while valid structured output can still contain unsupported claims. Human review remains a separate stage. These observations do not establish broad model reliability.

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

1. Preserve uploaded bytes, source hashes and extraction locations. Tables, text and supported media retain original bytes and extraction provenance. Format-specific extraction coverage remains explicit.
2. Extract media through verified adapters. Record which model or library performed OCR or transcription. An audio transcript passed to a text model is not native audio reasoning.
3. Have Bonsai propose a typed schema and classifications using bounded source context. Keep the proposal, validation errors and user corrections separately.
4. Have Bonsai select a versioned visualization specification with source field references. The current adapter renders Semiotic 3.10.3 charts to SVG and exposes source-linked controls in Svelte. Render checks must compare the actual marks with the compiled data. A successful library call alone does not establish correct visualization.
5. Render the specification with maintained components. Test selection, filtering, missing values, source links and annotations against the supplied data.
6. Preserve requests, responses, stage results and correction authors in MLflow. Export examples for a training loop with source provenance and review status. Do not turn provisional Codex review into human labels.

A successful stage does not establish success of subsequent stages. The desktop workflow is complete only when the file-to-interface examples execute through the model, survive interaction checks and retain their evidence.


## What the current runs add

The [two-video baseline](http://127.0.0.1:5210/#/experiments/32/runs/ba94fd5b3358436d973cb0ed37524de1) required a schema repair because the validator required structured records but the model context did not expose that requirement. The [replay](http://127.0.0.1:5210/#/experiments/32/runs/214d9e4a6eb344efab7912b8a10d6fc2) used identical source evidence, checkpoint metadata, and generation settings. Exposing the contract and adding comparison guidance produced a valid proposal in one call rather than two. Because two instructions changed together, this is a combined harness intervention on one development case.

The replay corrected the claim that missing arm-position detail constituted disagreement. It then attributed an identity disclaimer to both files when the explicit wording appeared in only one. Passing schema and citation-presence checks did not establish claim support. The review interface now places readable cited records beside each finding and lets a reviewer draft a targeted correction. It does not classify the claim as factual automatically.

This is where the two approaches meet in this implementation: the interpretation and plan provide a place to review assumptions before generation, while execution traces identify which contracts and checks need repair. The useful next measurement is whether a specific correction survives revision without losing supported evidence. Repeatedly adjusting a prompt until one example passes would not establish generalization. The audit artifacts distinguish engineering feedback from human-reviewed training examples.

The three-stage video study adds a concrete repair comparison. The failed and successful replays had identical source packets, model metadata and first responses. The original validator reported only that values and evidence were required; the revised message identified an unwanted id field and explained that the harness assigns IDs. The second response then removed that field while preserving the values and citations. Planning run e20aefa9a55a4432b6b7b6fea9ff65b6 and build run d6c60cce5ce849d8b98928bdff756e4a retain the evidence. This supports precise execution feedback as a harness intervention on this development case. It does not remove the need for source review, prove first-pass reliability, or establish performance on unseen desktop files.


## Separate interpretation errors from rendering errors

The email experiment provides a concrete example of the proposal review stage. Bonsai extracted two dated messages with issue counts of five and two. It retained the distinction between "Ready for review" and approval. Its initial plan grouped the line by review status, leaving each message in a separate series. An automated reviewer supplied a specific correction to group by project. The revised proposal preserved every structured record and citation while changing the grouping field. A file comparison also confirmed identical source packets and model metadata. The original and corrected planning runs remain separate from the build run in the [email evidence](live-audits/email-thread-correction.json).

The dated table experiment exposed a different cause. Bonsai requested separate team series correctly. The adapter supplied colors and produced two legend entries, but Semiotic drew one line because the adapter omitted lineBy. Correcting the adapter produced two lines from the same saved specification without another model call. The [render comparison](live-audits/dated-series-rendering.json) and [series check](live-audits/line-series-contract.json) preserve the baseline and correction. The series check establishes a count, not point-level accuracy or factual support.

Horthy's staged review approach suggests keeping the source interpretation and visualization choice reviewable before building. The email correction demonstrates that pattern on one synthetic case. Trivedy's trace-driven approach suggests turning observed execution failures into specific feedback and checks. The line adapter defect demonstrates why the renderer needs its own checks. These are applications of the authors' ideas to our observations, not experiments comparing the authors' systems. The source articles above were checked again on September 21, 2026.

## The original PDF separates coverage from completion

The original 79-page PDF exposed failures that the small development fixtures did not. Its first extraction contained 7,515 text characters and used no OCR. The newer extractor supplemented sparse embedded text, recovering 21,258 characters. The [extraction audit](live-audits/original-pdf-recovery.json) preserves the original failure and the separate recovery result. More characters do not establish transcription accuracy, and neither extraction interprets chart geometry or diagram relationships.

The 16K runtime could produce a valid proposal after reserving context for repair, but only 27 of 79 page records fit. The proposal assigned the same measurements to two bottlenecks, while a page containing a different measurement for the first section was omitted. The [reservation audit](live-audits/pdf-repair-reservation.json) records that attribution concern as an analyst finding requiring review. A smaller packet solved a capacity problem while leaving the user's complete-document task unresolved.

The 32K runtime accepted all 79 extracted page records, using the same model, runtime binary and projector. Its first call reached the generation deadline before completing the plan. The [runtime result](live-audits/pdf-32k-runtime.json) records that failure. The partial response contained five distinct records, with long source quotations and copied OCR noise. A later instruction to produce compact JSON and shorter supporting excerpts yielded a complete first response of 5,908 characters, compared with the earlier incomplete 13,213 characters. The [output comparison](live-audits/pdf-compact-output.json) is a development observation, not a repeated latency benchmark or proof that every form of looping was absent.

The compact response still violated several contracts. Repair feedback initially exposed only the first citation-count error, so the second response failed on an undeclared field. The revised diagnostics reported citation counts, missing field declarations and excess table columns together. In the [matched repair comparison](live-audits/pdf-combined-repair.json), the source snapshot, source packet, model configuration and first response matched the failed run exactly. One repair then produced a valid proposal while preserving all five structured records and their quotes. The proposal remains separate from a confirmed build and from human acceptance.

For our application of Horthy's approach, a reviewed source inventory must distinguish extracted content from omitted or uninterpreted evidence. The PDF shows why shortening context without preserving the task's required coverage can lose important relationships. For our application of Trivedy's approach, the useful execution feedback identifies independent contract failures together, so a bounded repair can address them in one attempt. The matched comparison supports that specific intervention on this repeated case. It does not compare the authors' systems or establish general reliability.

The next quality review should distinguish local operation timings from whole-training totals and cumulative improvements from incremental changes. Reviewers can now inspect all source records through pagination, and saving a review preserves the current page. Extraction refreshes retain earlier evidence, while reviews of an earlier extraction snapshot do not automatically become training candidates for the refreshed text. The current PDF proposal still needs a human decision about the intended comparison before its visualization is built.

## What must be measured next

| Stage | Evidence currently available | Evidence still needed |
| --- | --- | --- |
| Extraction | The original PDF recovery and synthetic email/media cases retain source bytes and locations | A fixed set of unseen desktop files with independently reviewed extraction coverage |
| Structuring and classification | The email correction and matched full-PDF repair preserve values and citations | Field-level judgments of omissions, unsupported values and useful classifications across files |
| Visualization choice | The status-grouping failure is recorded and a compiler check now rejects isolated line series | Reviewed judgments of whether a valid chart answers the user's actual question |
| Rendering and interaction | Tests cover line counts, dated values, point selection, source links and note drafts | Broader component coverage, dense overlap handling and independent point-position checks |
| Review and comparison | MLflow stores model attempts, authored fixes and automated review origins separately | Real reviewer decisions and a held-out comparison of frozen configurations |

The next comparison across multiple files should freeze source bytes, tasks, expected fields, model/runtime hashes and review criteria before inference. Compare the previous harness with the revised contracts on the same cases. Report extraction coverage, unsupported claims, correction retention, completed builds and interaction failures separately. Record latency and model calls as costs. Do not collapse a valid proposal, a completed build and an accepted interpretation into one success score.

The current experiments support specific repairs. They do not establish native multimodal accuracy, reliable handling of arbitrary desktop files, a trained model, or a deployed team product. Human review and the unresolved backup recovery remain explicit parts of the remaining work.
