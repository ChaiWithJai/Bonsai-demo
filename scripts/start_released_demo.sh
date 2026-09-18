#!/bin/sh
# Start a Bonsai 2 llama-server from configurable local paths.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
BIN="${BONSAI_LLAMA_SERVER:-$ROOT/bin/llama-server}"
MODEL="${BONSAI_RELEASE_MODEL:-$ROOT/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-PQ2_0.gguf}"
PROJECTOR="${BONSAI_RELEASE_MMPROJ:-$ROOT/models/bonsai2-gguf/27B/Ternary-Bonsai-2-27B-mmproj-BF16.gguf}"
NGL="${BONSAI_NGL:-999}"
CTX="${BONSAI_CTX:-8192}"
BATCH="${BONSAI_BATCH:-2048}"
UBATCH="${BONSAI_UBATCH:-256}"
LIB_DIR="${BONSAI_RUNTIME_LIB_DIR:-$(dirname "$BIN")}"
unset LD_PRELOAD
LD_LIBRARY_PATH="$LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export LD_LIBRARY_PATH
[ -x "$BIN" ] || { echo "Set BONSAI_LLAMA_SERVER to a built llama-server binary." >&2; exit 1; }
[ -s "$MODEL" ] && [ -s "$PROJECTOR" ] || { echo 'Download/verify the Bonsai 2 GGUF and mmproj first, or set BONSAI_RELEASE_MODEL/BONSAI_RELEASE_MMPROJ.' >&2; exit 1; }
exec "$BIN" -m "$MODEL" --mmproj "$PROJECTOR" \
  --host 127.0.0.1 --port "${BONSAI_PORT:-8081}" \
  -ngl "$NGL" -fa on -c "$CTX" -b "$BATCH" -ub "$UBATCH" \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0 \
  --jinja --webui-config-file "$ROOT/scripts/webui-config.json" "$@"
