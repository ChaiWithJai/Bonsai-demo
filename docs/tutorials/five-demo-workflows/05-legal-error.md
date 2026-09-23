# Inspect a legal overstatement in Bonsai

Separate a supported clause comparison from an unsupported conclusion, then inspect the recorded request and a later diagnostic without treating either as proof of causation.

Repository: [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo). Source revision: `bf425c5`. Companion cut: `05-legal-error-FINAL.mp4`, 52.8 seconds. Recorded September 23, 2026.

![Edited legal-error cut at 00:48 showing a separate diagnostic and the statement that cause is not established.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/05-legal-error-cut.png)

Figure 1. Frame at 00:48 of the edited cut. The measured replay is separate from the original answer.

## Before you start

Read [Review contract excerpts](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/03-legal-review.md) for the synthetic documents and prompt. Use the [legal error record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/legal-observed-error.json) to inspect the historical response without local inference. Interactive trace inspection requires your recording UI and a saved run; the author's local MLflow database is not included in the repository.

## Locate the unsupported claim

The recorded answer states:

> A service interruption that is not a material breach gives no termination right at all.

Supplied Section 12.1 states:

> A material service breach permits termination only after written notice and failure to cure within thirty days. A service interruption is not automatically a material breach.

The model moved from a condition in one clause to a conclusion about every possible termination right. The supplied excerpts do not cover every provision or legal basis.

Use the narrower review finding:

> The interruption alone does not establish a right under supplied Section 12.1. Other contractual provisions and legal bases were not supplied.

The finding limits the conclusion to the evidence. It does not establish whether another right exists.

## Inspect the run in Bonsai-demo

1. Open **Observability** and select the legal review conversation.
2. In **Chain**, select the answer's model exchange. Use **context** to inspect the supplied excerpts and **response** to locate the exact sentence above.
3. Compare the statement with Section 12.1. Record the missing scope: other contract provisions and any legal basis beyond the supplied text.
4. Preserve **configuration**, **runtime**, and the available **Open MLflow** trace link with the assessment. Do not replace the original response with the narrower wording.
5. If a measured diagnostic is attached, choose **Inspect measured replay activations**. Select a token and layer, then inspect the complete captured vector. A missing capture is an unavailable measurement, not evidence that the model had no relevant internal activity.

![Legal diagnostic in Bonsai Observability showing the processed token breach and a 5120-value vector at layer 31, step 8.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/05-legal-error-app.png)

Figure 2. Recorded app view of a separate teacher-forced diagnostic. The plot does not measure which values caused the overstatement.

## Check the review outcome

| Check | Expected review result |
| --- | --- |
| Does the summary match Section 12.1? | No. The summary omits materiality, notice, and cure conditions. |
| Does Section 12.1 establish that no other termination right exists? | No. The evidence is insufficient for that scope. |
| Has the original failure been retained? | Yes, in a separate recorded response or the public error record. |
| Does the diagnostic establish a cause? | No. It records values from a later execution. |

The [legal capture record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/legal-activation-evidence.json) reports 32 forced answer tokens, layers 0, 31, and 63, and 96 vectors with 5,120 values each. The original token IDs were unavailable, so the prefix and reasoning separator were reconstructed. The capture is not an exact replay of the original internal state.

Teacher forcing means supplying recorded answer tokens instead of generating a new answer. If you need a new capture, follow the [replay setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/NATIVE-UI-WORKFLOW.md#optional-replay-setup) and preserve its differences from the original execution.

## Define the next check

For a future review, require each conclusion to name the supplied provision and state what evidence is missing. Treat "no right at all" as a claim to investigate, not a phrase to ban mechanically. Broader evidence could support a broader conclusion.

Save the original claim, source passage, proposed correction, and reviewer decision separately. If you rerun the model with a revised prompt, record the new attempt independently. The cut documents one observed scope error; it does not validate a general legal evaluator or demonstrate a completed repair.

## Related workflows

- [Review contract excerpts](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/03-legal-review.md): reproduce the source comparison that preceded the overstatement.
- [Inspect a financial error](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/04-financial-error.md): use the same trace workflow with a deterministic arithmetic check.
