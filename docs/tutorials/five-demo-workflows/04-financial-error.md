# The ratio was correct. The dollar amount was wrong.

Bonsai calculated net debt of $69 million and approved earnings of $19 million, giving leverage of about 3.63x. Later in the same answer, it claimed $95 million of excess debt. The checked amount is $2.5 million.

The failure appears after a correct intermediate calculation. Checking only the ratio would miss it, even though the final dollar claim is straightforward to verify.

The [Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo) recording preserves the answer alongside its request and runtime information. That record gives a reviewer an exact claim to test. A later activation capture adds measurements, but does not explain why the model made the mistake.

![Edited financial-error cut at 00:39 showing the original USD 95 million claim beside a USD 2.5 million arithmetic check.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/04-financial-error-cut.png)

Figure 1. Frame at 00:39 of the edited cut. The correction is an editorial arithmetic check beside the preserved model output.

## Check the amount independently

The answer correctly calculated net debt of 69 and approved EBITDA of 19, giving about 3.63x leverage. It then claimed USD 95 million in excess debt. Run this independent calculation in a terminal:

```bash
python3 - <<'PY'
from decimal import Decimal
net_debt = Decimal('69')
ebitda = Decimal('19')
limit = Decimal('3.50')
permitted = limit * ebitda
excess = net_debt - permitted
assert excess == Decimal('2.50')
print(f'Permitted net debt: USD {permitted:.2f} million')
print(f'Excess net debt: USD {excess:.2f} million')
PY
```

Expected output:

```text
Permitted net debt: USD 66.50 million
Excess net debt: USD 2.50 million
```

## Reproduce or inspect the case

Start with [Reconcile a leverage covenant](https://gist.github.com/ChaiWithJai/f66f84aab4141232083afab7254cfa38). For the historical case, use the public [financial error record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/financial-observed-error.json). To inspect a run interactively, use your own recording UI and its local request artifacts. A fresh clone does not contain the author's chat database or MLflow store.

## Inspect the run in Bonsai-demo

1. Open **Observability** from the sidebar and select the conversation created by your document review.
2. In **Chain**, select the model exchange containing the answer. Exclude auxiliary requests that generate chat titles.
3. Compare **context** and **response**. Confirm that the request includes the lender evidence and that the response contains the statement under review.
4. Inspect **configuration** and **runtime**. Preserve the model identity, settings, and recorded timing with the failure.
5. Follow **Open MLflow** if a trace link is present. A trace identifier from the historical example resolves only in the store that contains it.
6. If an attached diagnostic exists, choose **Inspect measured replay activations**. Select a token and layer, then choose **Inspect all 5120 captured values** for the demonstrated model. If no diagnostic exists, record that absence. Generating a new replay requires the separate [replay setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/NATIVE-UI-WORKFLOW.md#optional-replay-setup).

![Financial diagnostic in Bonsai Observability showing forced answer tokens and a full 5120-element vector for layer 31, step 8.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/04-financial-error-app.png)

Figure 2. Recorded diagnostic view. The horizontal axis of the full-vector plot is activation dimension, not token position.

## What the activation capture can establish

The [financial capture record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/financial-activation-evidence.json) reports 32 recorded answer tokens passed through a reconstructed prefix. Three selected layers, 0, 31, and 63, produced 96 vectors of 5,120 values each.

Teacher forcing means supplying the recorded tokens to the model rather than asking it to generate those tokens again. The capture used a fresh context and reconstructed the reasoning separator because the original stream did not preserve token IDs. The vectors belong to that later diagnostic. They neither recover the original activations nor identify a cause for the arithmetic error.

## Turn the failure into a calculation check

Keep the failure and proposed correction as separate records. Before accepting an excess-debt amount, calculate `net_debt - limit × approved_EBITDA` and compare the result in the same units. A negative result represents headroom, not positive excess.

Rerun the same source packet after adding a calculation check, then compare the new result with the original. The cut proposes that repair; it does not demonstrate that a repair was deployed or that recurrence was prevented.

## Continue the review

- [Reconcile a leverage covenant](https://gist.github.com/ChaiWithJai/f66f84aab4141232083afab7254cfa38): reproduce the input packet and review prompt.
- [Inspect a legal overstatement](https://gist.github.com/ChaiWithJai/79df3593a0744961cb49967df56bdb6b): contrast an arithmetic check with a claim that requires scope review.

<details>
<summary>Recording and source revision</summary>

Repository: [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo). Source revision: `bf425c5`. Companion cut: `04-financial-error-FINAL.mp4`, 65.8 seconds. Recorded September 23, 2026. The companion filename identifies the original edited cut; screenshots are pinned to the published repository assets.

</details>
