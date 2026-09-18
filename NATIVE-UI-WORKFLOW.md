# Native Bonsai UI, BrowserOS, and MLflow

This workflow wraps the stock llama.cpp UI with Prism branding, local recording,
MLflow traces, BrowserOS MCP relay support, and an observability view. It does not
change inference bodies or inject answers.

## Build the UI

Build llama.cpp first, then point the Prism builder at the llama-ui source:

```bash
python3 scripts/build_prism_ui.py \
  --source llama.cpp/tools/ui \
  --output .cache/bonsai/prism-ui
```

If your llama.cpp checkout stages UI sources somewhere else, pass that directory
with `--source`. The source must already have its Node dependencies installed.

## Immediate Mac-to-Linux Recording Path

Use this when the model servers are already running on a Linux host and BrowserOS
Neo is running on the Mac at `127.0.0.1:19010/mcp`.

On the Mac, create the tunnel only if one is not already running:

```bash
ssh -N -o ExitOnForwardFailure=yes \
  -L 8088:127.0.0.1:8088 \
  -L 5210:127.0.0.1:5210 \
  -R 127.0.0.1:19010:127.0.0.1:19010 \
  <ssh-user>@<ssh-host>
```

If a recording UI is already serving on port 8088, do not start a duplicate. For a
fresh Linux host, install the recording dependencies and start MLflow:

```bash
python3 -m venv .venv-recording
. .venv-recording/bin/activate
python -m pip install -e '.[recording]'
mlflow ui --backend-store-uri sqlite:///$PWD/.cache/bonsai/mlflow.db \
  --host 127.0.0.1 --port 5210
```

Then start the recording UI against the already-running Bonsai server. Adjust paths
for your checkout and local virtual environment:

```bash
python3 scripts/recording_ui.py \
  --port 8088 \
  --upstream http://127.0.0.1:8081 \
  --static-dir .cache/bonsai/prism-ui/dist \
  --tracking-uri sqlite:///$PWD/.cache/bonsai/mlflow.db \
  --records-dir $PWD/.cache/bonsai/native-ui-records \
  --comparison-records-dir $PWD/.cache/bonsai/comparison-records \
  --browseros-url http://127.0.0.1:19010/mcp \
  --release-manifest .cache/bonsai/release-manifest.json \
  --replay-activity-port 8081 \
  --replay-activity-port 8082
```

Open `http://127.0.0.1:8088` on the Mac. Open MLflow at
`http://127.0.0.1:5210`.

## Optional Replay Setup

Replay capture needs a verified model manifest, an instrumented capture binary, and
the matching llama.cpp shared libraries. The model helper writes manifests under
the destination model directory:

```bash
python3 scripts/model_store.py prism-ml/Ternary-Bonsai-2-27B-gguf \
  models/bonsai2-gguf/27B \
  --patterns '*PQ2_0.gguf,*mmproj*BF16.gguf'
```

Build the capture executable after llama.cpp shared libraries are available:

```bash
BONSAI_RUNTIME_LIB_DIR=$PWD/bin \
scripts/capture_activations.sh
```

Pass the resulting binary, runtime library directory, and release manifest to
`recording_ui.py` with `--replay-capture-binary`, `--replay-runtime-lib-dir`, and
`--release-manifest`.

## Native Mac Notes

Basic chat and recording can run on macOS if the upstream llama-server and Python
dependencies are available locally. Activation replay capture is currently guarded
as Linux-only because the packaged capture path links against llama.cpp shared
libraries and verifies loaded libraries via `/proc/<pid>/maps`. On macOS, the UI
shows replay as unavailable until a Metal-compatible capture build and verifier are
added and tested on that hardware.

If you run large image prompts on Metal, Vulkan, or CPU, the Bonsai scripts cap
large images to about 1024 vision tokens by default. Keep that cap for snappier
image answers, or set `BONSAI_IMAGE_MAX_TOKENS=0` when full image detail matters
for OCR, screenshots, or small text.

## What Gets Recorded

The recorder persists request and response bytes for local completion calls and
proxied BrowserOS MCP exchanges. Headers such as credentials are not stored by the
recorder, but prompts, model output, rendered tool context, BrowserOS page text, and
vector artifacts can still be sensitive. Keep `.cache/`, MLflow databases, model
files, browser snapshots, and replay artifacts out of Git.
