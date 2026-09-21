# Sampling comparison and native data checkpoint

September 21, 2026. All four trials resumed copies of the same verified W1 source revision and conversation. They used the same task request, native context preflight, compiler, browser acceptance checks, output limits, and new repeated-patch stop condition. No sampled configuration passed W2, so none was promoted.

| Profile | Seed | Result | Applied patches | MLflow run |
| --- | --- | --- | --- | --- |
| Historical greedy, thinking off | 42 | Stopped on second occurrence of the same unmatched fragment | 0 | d68e73489217458bb16f101cb7fb38fd |
| Documented instruct | 42 | Exhausted browser repair budget | 1 | fbbde73f3dbc4e21825d8147e69436dc |
| Documented instruct | 43 | Exhausted browser repair budget | 2 | 8fa4ce41aad14eafa3f6ac7a484196ea |
| Documented instruct | 44 | Exhausted model-call budget without verification | 2 | ff4bfceb2d894fd3b738df398a430acf |

Every completed trial's whole-attempt trace was fetched back from MLflow. The first comparison launch exposed a separate exporter setup bug: the client URI was configured, but the process-global tracing URI was not. Its greedy run `5e3bdf6319404708b53bf87d904e86ba` retained artifacts but lacked the whole trace. The following instruct run `f04515d4a7f2495daffc4b0e542b11b0` was interrupted when the bug was verified. Both are retained and excluded from the comparison. The corrected runner tests trace export before inference and after each attempt.

These are development examples, not a model success-rate estimate. The trials ran sequentially on the warm Metal service; context caching and an overlapping CPU/disk backup make wall-clock differences unsuitable for a speed comparison. Sampled seeds were 42, 43 and 44. The greedy control used 42. The documented instruct profile is a bundle of sampling changes, not an isolated temperature experiment.

## What changed the next action

Sampling allowed patches in all three instruct trials, but it did not solve the task. Two generated sources used `$derived(() => {...})` and then consumed that function as an array. Svelte 5 requires `$derived.by(() => {...})` for that form. Another trial retained `showAllNotes` when selecting a new record, so the previous record's note remained visible. Repeated checks of unchanged source consumed the browser repair budget.

The next harness intervention should provide a small, versioned Svelte 5 reference and the actual source lines around failed edits. It should separately track repeated browser failures on unchanged revisions. Keep the same source revision and task for that comparison. Do not change the acceptance check to accept these failures. The medium-thinking profile is implemented, but has not yet been tested or promoted.

## Native source-data workflow

The native Data tab at http://127.0.0.1:5258/#/workspace now reuses the frozen prototype's intake and record-review modules. It accepts CSV, TSV, JSON, JSONL, text and Markdown, preserving original bytes, source hashes, record IDs and locations. Images, PDFs, audio and video are stored with an explicit pending-extraction state. No media extraction is claimed here.

Reviews remain separate from source values. They include reviewer kind, source snapshot, predecessor event and correction. Exports preserve all review history and include training candidates only from the latest human-declared accepted or corrected records. No training runs automatically, and reviewer identity remains self-declared.

A BrowserOS Neo test uploaded a synthetic JSON file containing zero and null. It saved a correction with reviewer kind `test`, reloaded the page and verified persistence. Export `a81288d6156747fd999576e23621b1d7` in MLflow experiment 32 contains one test review, zero training candidates and the unchanged original zero/null values. An earlier export with zero reviews is retained: a browser automation text-selection error had produced invalid JSON before save. It is not counted as a successful review.

Validation: 146 Python tests passed; the branded UI passes Svelte checking with zero errors and warnings; all changed Svelte components passed the MCP CLI autofixer; the production build passed. Desktop and mobile source-review captures passed, including original-value and persisted-review assertions. These are automated checks, not human design labels.

The original W1 workspace on port 5257 was not modified by the comparison or source-review fixture. The native Data panel does not yet feed uploaded records into generated projects. Classification, Semiotic-based project generation, image/video extraction, audio transcription and the complete training-candidate iteration remain integration work. The full goal remains open.
