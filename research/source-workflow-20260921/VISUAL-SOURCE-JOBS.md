# Native visual source jobs

Images and videos have a Read visual content with Bonsai action in Workspace. A persisted job shares the model reservation with planning and editing. The source checksum is checked, previous extraction is retained, requests and responses are saved, and model-extracted rows remain unreviewed. A failure or cancellation leaves the prior extraction in place. Concurrent source changes prevent applying stale extraction results.

The extraction unit and validation code reuses workbench/media.py from the frozen bonsai-generative-ui prototype at a69afd8290de71a18755f934516a0ed9f649afe6. Images are read as one visual input. Videos up to five minutes sample a frame every 15 seconds. Audio is not included in this visual pathway. A ten-minute job budget and bounded per-call provider apply; no automatic inference retry is added.

The native video review plays the original with byte-range support and seeks to the timestamp of a selected extracted record. Sampling limitations are shown in the UI and included in the source profile sent to the proposal model. They do not establish motion understanding or exhaustive coverage.

The reused sixteen-second static-table video completed in 27.901 seconds. It produced six source-bound records, three at each of 0 and 15 seconds. Both frames matched the five fields of the three expected observations, including numeric types. This remains a reused constructed development fixture. It is not a natural-video benchmark or human verification.

Extraction job: 2f6688b129984c9a8d418f1676138ef8. MLflow run: aa11ec544fd1462bbefd3bc62881d707, experiment 32. Desktop and mobile browser checks verified seeking to the second sampled frame and selecting a source record. No review or user confirmation was submitted.

The runtime owner is now .cache/workspace-vision-jobs-live-20260921/process.json; upstream 62196, UI 5257. SIGUSR1 requests an idle proxy reload while retaining the model. Active Workspace jobs cause that reload request to be declined. The old vision runtime was shut down before claiming the GPU queue again.

The audio checkpoint backup failed during MongoDB GridFS upload after a connection closure. Docker reports an input/output error when reading the container log and the expected host port is unavailable. No new archive restore is claimed. An older disposable restore copy was removed to recover space; the preceding verified archive and latest verified restore remain retained. A Docker-wide restart was not performed.

The follow-on video-to-proposal job acb2b9ed55f94dcfbb21db634419aa8d failed after two model calls, run 035466e1af1446499bea150cd9aeb3a1. A finding cited all six source records, violating the five-reference limit. The existing generic validation message described an ID error and did not identify the count violation; the model repeated the same mistake. Validation feedback now distinguishes an excessive citation count from an unknown source ID and tells the model to split the finding. A regression test verifies the precise feedback. The failed model run is not relabeled successful. A new model attempt is still needed to validate the repair.

169 full Python tests passed before the feedback-only change; four packet/feedback tests passed afterward. Svelte checks and build passed, as did both video browser checks. The retained bind:this use supports imperative media seeking. The muted source video has no generated caption track; no audio understanding is claimed.
