#!/bin/sh
# Start an optional local Qwen control server from configurable local paths.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BIN="${QWEN_LLAMA_SERVER:-${BONSAI_LLAMA_SERVER:-$ROOT/bin/llama-server}}"
LIB="${QWEN_RUNTIME_LIB_DIR:-${BONSAI_RUNTIME_LIB_DIR:-$(dirname "$BIN")}}"
MODEL="${QWEN_CONTROL_MODEL:-$ROOT/models/qwen3.8-27b/Qwen3.8-27B-UD-IQ2_XXS.gguf}"
[ -x "$BIN" ] || { echo "Set QWEN_LLAMA_SERVER or BONSAI_LLAMA_SERVER to a built llama-server binary." >&2; exit 1; }
[ -s "$MODEL" ] || { echo 'Qwen control model missing; set QWEN_CONTROL_MODEL to a local GGUF.' >&2; exit 1; }
unset LD_PRELOAD
LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LD_LIBRARY_PATH
exec "$BIN" -m "$MODEL" --host 127.0.0.1 --port "${QWEN_CONTROL_PORT:-8082}" \
  -ngl "${QWEN_NGL:-${BONSAI_NGL:-999}}" -fa on -c "${QWEN_CTX:-8192}" -b "${QWEN_BATCH:-2048}" -ub "${QWEN_UBATCH:-256}" -np "${QWEN_PARALLEL:-1}" \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0 --jinja "$@"
