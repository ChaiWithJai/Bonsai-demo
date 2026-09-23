# Editorial review of the five Bonsai guides

The revision gives each guide one claim that readers can check, then explains how to reproduce or inspect it. Setup, filenames, and revision metadata no longer interrupt the opening explanation.

## Writing rules

Applied [mine-writing-rules](https://github.com/docwriter-org/mine-writing-rules/tree/68b9a2258073d20e60467573aebe5eeb8b2db9d7) at revision `68b9a2258073d20e60467573aebe5eeb8b2db9d7`. The rules were read from its flat rule corpus, with these rules selected for explanatory technical articles:

| Rule | Application |
| --- | --- |
| R348 and R349 | Begin with the result or problem, without announcing the document. |
| R585 | Give each article a reader, a subject, and one central point. |
| R588 | Explain a reusable insight beyond the sequence of interface controls. |
| R797 | State what each screenshot demonstrates in its caption. |
| R428 | Review structure before sentences and punctuation. |
| R429 | Move distracting setup and metadata out of the opening. |

The plain-writing skill supplied the sentence-level review. Technical terms such as leverage remain where they have a precise financial meaning. The articles do not imitate an author's voice or claim Linux Foundation approval.

## Comparison with ten DX Tips posts

The selection favors teaching, concrete demonstrations, technical explanation, and distribution. It is an editorial selection of ten strong references from the 48-post archive, not a traffic ranking. All ten article bodies were read. Linked talks in the pitches collection were not independently watched for this review.

| Reference | Useful principle | Change in these guides |
| --- | --- | --- |
| [Stop writing long boring titles](https://dx.tips/titles) | A title should make a specific promise. | Replace generic product-and-task titles with the particular finding. |
| [Make videos devs love](https://dx.tips/video) | Teach a useful capability and earn attention early. | Explain what the viewer can inspect before listing controls. |
| [Make Micro Courses](https://dx.tips/micro-courses) | Organize lessons around a useful progression. | Link the financial and legal comparisons to their respective failure investigations. |
| [The Master Builder](https://dx.tips/master-builder) | Demonstrate useful work through a concrete build. | Keep runnable inputs, actual interface steps, and expected results. |
| [DX @ Anthropic: Sowing & Reaping](https://dx.tips/dx-anthropic-sowing-reaping) | Explain lessons learned through actual use. | Retain the recorded mistakes rather than presenting an uninterrupted success story. |
| [Work on your Devtool Money Shot](https://dx.tips/money-shot) | Give the reader a visual that explains the central message. | Put a captioned evidence frame immediately after the opening. |
| [Benefit Layers](https://dx.tips/benefit-layers) | Explain direct effects instead of vague business benefits. | Describe payment inspection, definition comparison, and claim checking without promising general accuracy. |
| [The Best DevTools Pitches of All Time](https://dx.tips/pitches) | The collection favors concrete demonstrations. | Our editorial inference is to give every guide an observable result; the collection itself is not a writing rubric. |
| [Don't Let a Bad Abstraction Cost You 2 Years](https://dx.tips/dont-let-a-bad-abstraction-cost-you-2-years) | Preserve access to the underlying work when a simplified view is insufficient. | Readers can move from the result to fixtures, exact responses, and runtime evidence. This is an application of the product lesson to documentation. |
| [The Hub+Spoke Content Strategy](https://dx.tips/hubspoke-strategy) | Connect substantial source material with channel-specific distribution. | Keep repository copies and setup together, with linked public gists for each case. |

## Review of each guide

| Guide | Central point and intended reader | Old draft problem | Revision and assurance |
| --- | --- | --- | --- |
| Bond pricing | A reader learning bond math must confirm the schedule and yield before pricing. | Opened with an interface task and metadata. | Lead with the worksheet error; independently check both prices and the final payment. |
| Financial diligence | An analyst must reconcile definitions before comparing ratios. | Buried the source disagreement below setup. | Lead with 2.73x versus 3.63x; retain the later wrong dollar amount and link its investigation. |
| Legal review | A document reviewer must preserve exceptions and conditions. | Treated comparison as a list of controls. | Start with the thirty-day versus ninety-day distinction; check all findings against the supplied excerpts. |
| Financial error | An engineer must test final numeric claims even after correct intermediate arithmetic. | Led with trace navigation. | Start with $95 million versus $2.5 million; retain executable Decimal verification and separate diagnostic limits. |
| Legal overstatement | A reviewer must limit a conclusion to the evidence supplied. | Led with diagnostic procedure. | Start with the exact unsupported sentence; distinguish insufficient evidence from a proven contrary legal conclusion. |

## Assurance passes

1. Structural review checked the title, opening claim, evidence order, and next action in each article against the selected writing rules and references.
2. Evidence review checked fixture hashes, pinned source paths, quoted failure records, bond arithmetic, and the runnable financial calculation. No new inference was needed. A new model run may produce different wording or different errors.
3. Publication review checks the five existing public gist IDs against their local Markdown, verifies rendered screenshots and cross-links, and keeps the repository copies on the personal fork.

The financial and legal packets are synthetic. The activation measurements came from later teacher-forced executions with reconstructed prefixes, so they do not establish the causes of the original failures. Fresh-install validation and general model-accuracy evaluation are outside the evidence provided by these articles.
