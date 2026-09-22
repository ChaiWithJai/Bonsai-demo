# Two Bonsai profiles on three frozen desktop tasks

Instruct retained the expected data in all three development tasks. Bounded reasoning omitted the second email record. Both profiles produced valid proposals in one call, and both misstated the observation count in the PowerPoint explanation. A valid proposal is therefore an inadequate success measure for this workflow.

| Task | Instruct | Bounded reasoning |
| --- | --- | --- |
| Dated CSV | All 6 observations; separate team lines; 18.711 seconds | All 6 observations; separate team lines; 37.813 seconds |
| Email thread | Both messages; table; 22.164 seconds | Only 1 of 2 messages; table; 48.297 seconds |
| PowerPoint | All 4 observations, including zero and null; table; prose says 2 observations; 37.955 seconds | All 4 observations, including zero and null; table; prose says 6 observations; 60.537 seconds |

The PowerPoint instruct response used `date` instead of the frozen `review_date` field name. The automatic analysis correctly left that value comparison unresolved. A separate Codex review mapped the field and verified the expected values. The original automatic result is preserved. All emitted structured quotes in the email and PowerPoint responses occur verbatim in their sources. Quote presence does not establish support for every assertion.

Each pair received identical archived sources, source context, harness hashes, model/runtime metadata, and first-request messages. The changed request fields were temperature, top-p, presence penalty, chat-template reasoning settings, and thinking-token allowance. This compares two combined profiles, not reasoning in isolation. Both used seed 42 on the resident Bonsai 2 27B runtime, with 32K context and the existing 4,096-token output allowance. The prior legacy-greedy default was not included.

These are previously used synthetic development cases. There was one attempt per profile and case, with no manual correction or build confirmation. The existing schema-repair policy was unchanged; none of the six attempts required a second call. Server cache was not reset. Order alternated by case. Observed elapsed times describe this run and do not establish a general speed advantage. No human acceptance, new interface build, or held-out evaluation is claimed.

## Implication for the harness

Keep data retention, claim support, chart usefulness, and schema validity separate. The email omission and the contradictory PowerPoint counts would be hidden by a single proposal-ready score. Keep the current default unchanged until a broader reviewed comparison exists. Give people a way to revise the view while preserving already structured data and citations; choosing a chart should not require re-extracting every record.

The frozen protocol, runner, original analysis, separate field review, and MLflow run IDs are stored alongside this report. `results.json` links every attempt to its planning run. Nothing was exported as a human-reviewed training example. New MongoDB backup verification remains unavailable.

To inspect the saved study again without inference, run from the repository root:

```sh
python3 research/harness-alignment/profile-study-20260922/analyze.py \
  --results .cache/profile-study-20260922 \
  --workspace .cache/workspace-live-v3-20260921/workspace \
  --output /tmp/profile-study-analysis.json
```

The runner requires a new output directory and the exact frozen runtime metadata. It does not restart or retry a generation. Polling failures keep observing the same job. It starts six real model attempts, so rerun it only as an intentional new experiment.
