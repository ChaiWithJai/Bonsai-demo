# Vision-capable native Workspace runtime

The native Workspace now runs the cached Bonsai 2 27B PQ2_0 checkpoint with its matching Q8 vision projector. Both model and runtime hashes are checked, the shared GPU queue is claimed after three quiet checks, and the projector SHA256 is verified before launch. Image input is capped at 1,024 tokens. The runtime ownership code reuses the frozen bonsai-generative-ui implementation at a69afd8290de71a18755f934516a0ed9f649afe6, with local copies of its small process/hash helpers and the explicit image-token cap.

The new scripts are workspace_runtime.py and launch_workspace_runtime.py. The launcher accepts a pinned config, a new evidence output directory, and a JSON proxy command. It updates the proxy upstream and release-manifest arguments after the model becomes ready. The proxy retains the existing workspace directory. Environment variables configure the optional audio worker as before.

Current owner: .cache/workspace-vision-live-20260921/process.json. Current proxy command and runtime identity are beside that file. The native UI remains on port 5257; model upstream is 60752. The old owner and duplicate proxy on 5255 were stopped cleanly. Do not reuse the old 64223 upstream or old text-only launch command. Stopping the new proxy ends this owned runtime context and stops its model; inspect jobs before a deliberate deployment restart.

The existing pending PDF proposal and all three saved workspaces survived the restart. No proposal was confirmed.

A reused constructed table image completed native vision inference in 10.30 seconds. All 15 visible values matched as text. Strict typed equality failed because three numeric download counts were returned as strings. The failure and raw response are preserved, not repaired into an apparent model success. The subsequent source schema conversion already supports explicit numeric conversion, but this run does not test that whole pipeline. It is a reused development example, not held-out visual accuracy.

Recorder trace: tr-372b1d14c8c30180a70123896d2848e4. Request b459e07a10f748519969c58674d58af0. The recorder's separate activation replay failed because that capture backend is verified only on Linux; the HTTP exchange itself completed successfully. This run does not establish activation-level instrumentation on macOS.

Native Workspace source uploads still use Apple Vision OCR by default. Connecting Bonsai visual extraction and sampled video evidence to the source job workflow remains required. Enabling the server alone is not completion of those user workflows.
