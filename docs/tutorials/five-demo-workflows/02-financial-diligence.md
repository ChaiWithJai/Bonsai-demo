# The same company has two leverage ratios

Management reports leverage of 2.73x. The lender's definition produces 3.63x, above the 3.50x covenant limit. Both calculations describe the same company on the same measurement date.

The disagreement starts with which cash and earnings adjustments count. Management deducts all $24 million of cash and adds $4 million to earnings. The lender excludes $9 million of restricted cash and approves only $1 million of the requested adjustment.

The recorded [Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo) review makes those differences visible beside the supporting passages. It also makes a later arithmetic mistake. A useful review needs to preserve both results.

![Edited financial-diligence cut at 00:50 with management and lender definitions side by side.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/02-financial-diligence-cut.png)

Figure 1. Frame at 00:50 of the edited cut. The source table distinguishes requested adjustments from approved adjustments.

## Follow the calculation

All amounts below are USD millions. Both documents measure the business on June 30, 2026. EBITDA means earnings before interest, taxes, depreciation, and amortization.

| Measure | Management basis | Lender-approved basis |
| --- | ---: | ---: |
| Gross debt | 84 | 84 |
| Eligible cash | 24 | 24 - 9 = 15 |
| Net debt | 60 | 69 |
| EBITDA | 18 + 4 = 22 | 18 + 1 = 19 |
| Net leverage | 60 / 22 = 2.73x | 69 / 19 = 3.63x |

Under the supplied lender definition, 3.63x exceeds the 3.50x limit by about 0.13x. It is not 3.63 times the limit. The permitted net debt is `3.50 × 19 = 66.5`, so the excess is `69 - 66.5 = 2.5` million dollars.

![Recorded financial answer showing supporting quotes and an incorrect later claim of USD 95 million excess debt.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/02-financial-diligence-app.png)

Figure 2. Original app output. The visible USD 95 million claim is an observed error; the checked amount is USD 2.5 million.

## Try it in New chat

Use the branded Bonsai recording UI described in the [series setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/README.md#run-the-recording-ui). Download the synthetic [management summary](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/evals/demos/financial/management-summary.txt) and [lender review](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/evals/demos/financial/lender-review.txt) using GitHub's raw-file download.

1. Open **New chat** and attach both text files.
2. Send the recorded prompt below. No cloud tool is required for this example.

```text
Review these two synthetic development documents. Does the company satisfy
the stated leverage covenant under the lender definition? Calculate eligible
cash, net debt, approved EBITDA and leverage. Compare the management claim
with the controlling source. Quote the source passages that support your
conclusion. Use only these attachments. Do not use cloud tools.
```

3. Match each quoted passage to the original attachment. Check which cash may reduce debt and which earnings adjustments the lender approved.
4. Recalculate the comparison table above. Keep the measurement date and units unchanged.
5. Read the entire answer, including its final paragraph. In the recorded run, the model calculated the ratio correctly and then gave an incorrect dollar amount.

## Check the last paragraph too

If the answer nets all cash, point to the lender's restriction on 9 million. If it adds back all 4 million, distinguish the request from the 1 million approval. If a quote cannot be found in either attachment, leave the claim unverified.

A new run may avoid the recorded mistake or produce a different one. Preserve the output you receive rather than inserting the historical error. The full recorded answer and original prompt remain in the [financial error record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/financial-observed-error.json).

## What the recording proves

The recording shows one local model review of a synthetic packet. It demonstrates source comparison and an observed arithmetic failure, not a measured error rate across financial work. The video condenses the interaction and includes editorial comparison graphics. Its duration is not inference latency. The recording does not demonstrate an automatic arithmetic repair.

## Continue the review

- [Inspect the financial error](https://gist.github.com/ChaiWithJai/ae3046a50213aba9903838256cbec6a8): trace the incorrect USD 95 million statement and check the calculation.
- [Review contract excerpts](https://gist.github.com/ChaiWithJai/c1c134d1448948fa379b1d62beffce9f): apply the same claim-to-source comparison to exceptions and conditions.

<details>
<summary>Recording and source revision</summary>

Repository: [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo). Source revision: `bf425c5`. Companion cut: `02-financial-diligence-FINAL.mp4`, 85.4 seconds. Recorded September 23, 2026. The companion filename identifies the original edited cut; screenshots are pinned to the published repository assets.

</details>
