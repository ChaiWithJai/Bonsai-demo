# Release Migration Notes

This fork keeps the recording demo source-only. It does not publish model files,
local runtime binaries, MLflow databases, captured conversations, or replay vectors.

For a local Bonsai 2 service, use `scripts/start_released_demo.sh` with explicit
paths when your runtime or model layout differs:

```bash
BONSAI_LLAMA_SERVER=$PWD/bin/llama-server \
BONSAI_RUNTIME_LIB_DIR=$PWD/bin \
BONSAI_RELEASE_MODEL=$PWD/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf \
BONSAI_RELEASE_MMPROJ=$PWD/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-mmproj-BF16.gguf \
BONSAI_CTX=8192 \
scripts/start_released_demo.sh
```

For an optional Qwen control, use:

```bash
QWEN_LLAMA_SERVER=$PWD/bin/llama-server \
QWEN_RUNTIME_LIB_DIR=$PWD/bin \
QWEN_CONTROL_MODEL=$PWD/models/qwen3.8-27b/Qwen3.8-27B-UD-IQ2_XXS.gguf \
scripts/start_qwen38_control.sh
```

Keep context, batch sizes, GPU offload, and image-token caps tuned to the actual
machine. Two 27B servers plus replay capture can exceed laptop memory; on tighter
hardware run one server at a time or leave replay disabled.
