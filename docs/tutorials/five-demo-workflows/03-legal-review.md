# A contract summary loses the conditions that change the answer

The summary promises deletion of all customer data within thirty days. The agreement gives active systems thirty days, but permits encrypted recovery backups for up to ninety days with restricted access. Reducing the agreement to one deadline changes the obligation.

A recorded review in [Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo) compares a fictional agreement with its summary. The model identifies the deletion conflict, an exception to the liability cap, and conditions on termination. Each finding can be checked against a supplied section.

The response then goes too far on termination. Finding the summary's mistakes does not establish that every sentence of the model's explanation is supported.

![Edited legal-review cut at 00:35 showing the notice and cure requirements in Section 12.1.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/03-legal-review-cut.png)

Figure 1. Frame at 00:35 of the edited cut. Section 12.1 conditions termination on material breach, notice, and failure to cure.

## Keep the exceptions and conditions

| Summary claim | Supplied passage | Supported finding |
| --- | --- | --- |
| All claims are capped at twelve months of fees. | Sections 8.1 and 8.2 | The stated cap excludes fraud and willful misconduct. |
| All customer data is deleted within thirty days. | Sections 11.1 and 11.2 | Active systems have a thirty-day deadline. Encrypted recovery backups may remain for up to ninety days, with restricted access. |
| Any interruption permits immediate termination. | Section 12.1 | The clause requires material breach, written notice, and failure to cure within thirty days. An interruption is not automatically material. |

The recorded response identified all three authored conflicts. It also asserted that a nonmaterial interruption gives "no termination right at all." The excerpts do not establish that broader claim.

![Recorded legal answer showing Section 12.1 and the unsupported statement that a nonmaterial interruption gives no termination right at all.](https://raw.githubusercontent.com/ChaiWithJai/Bonsai-demo/648c8f341bd9136032c637505c65ac996eec1726/docs/tutorials/five-demo-workflows/images/03-legal-review-app.png)

Figure 2. Original app output. Review the quoted clause and the later overstatement separately.

## Try it in New chat

Use the branded Bonsai recording UI described in the [series setup](https://github.com/ChaiWithJai/Bonsai-demo/blob/main/docs/tutorials/five-demo-workflows/README.md#run-the-recording-ui). Download the synthetic [review summary](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/evals/demos/legal/review-summary.txt) and [agreement excerpts](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/evals/demos/legal/agreement-excerpts.txt) using GitHub's raw-file download.

The excerpts describe a fictional agreement. They do not supply the complete contract or establish rights under applicable law.

1. Open **New chat** and attach both text files.
2. Send the recorded prompt below.

```text
Review these two synthetic development documents. Check the summary against
the agreement. Identify each material contradiction involving liability,
deletion and termination. Quote the controlling passage and explain the
practical difference. Use only these attachments. Do not use cloud tools.
```

3. Read each quoted section beside the summary claim it addresses. Follow the cross-reference from Section 8.1 to Section 8.2.
4. Compare the result with the findings above. Preserve qualifiers such as "active systems," "up to," and "material."
5. Read the explanation after the quoted clauses. A correct quotation can still be followed by an unsupported conclusion.

## Keep the correction within the supplied text

If the answer treats the liability cap as universal, check Section 8.2. If it gives one deletion deadline, separate active systems from recovery backups. If it claims that no termination right exists anywhere, ask which supplied passage supports that scope.

A review correction can use narrower wording: "The interruption alone does not establish a right under supplied Section 12.1." Other provisions and legal bases were not supplied. The formulation is a review correction, not a demonstrated corrected model run.

## What the recording proves

The [legal error record](https://github.com/ChaiWithJai/Bonsai-demo/blob/bf425c5c4195ac061dddd4e4b31f510366b6f0a6/docs/demos/legal-observed-error.json) contains the complete response, prompt, source hashes, and trace identifier. The example measures neither general legal accuracy nor professional approval. The 48.1-second cut uses editorial trimming and source crops; it is not a continuous recording of inference.

## Continue the review

- [Inspect a legal overstatement](https://gist.github.com/ChaiWithJai/79df3593a0744961cb49967df56bdb6b): isolate the unsupported sentence and inspect its recorded context.
- [Reconcile a leverage covenant](https://gist.github.com/ChaiWithJai/f66f84aab4141232083afab7254cfa38): compare conflicting definitions while retaining the source evidence.

<details>
<summary>Recording and source revision</summary>

Repository: [ChaiWithJai/Bonsai-demo](https://github.com/ChaiWithJai/Bonsai-demo). Source revision: `bf425c5`. Companion cut: `03-legal-review-FINAL.mp4`, 48.1 seconds. Recorded September 23, 2026. The companion filename identifies the original edited cut; screenshots are pinned to the published repository assets.

</details>
