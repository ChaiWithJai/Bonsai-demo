#!/bin/sh
# Build the standalone replay capture executable. Running a replay is a separate
# explicit step via capture_activations_replay.py.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
OUT="${BONSAI_CAPTURE_BUILD_DIR:-$ROOT/.cache/bonsai/activation-diagnostic/bin}"
LIB="${BONSAI_RUNTIME_LIB_DIR:-$ROOT/bin}"
SOURCE="${BONSAI_CAPTURE_SOURCE_DIR:-$ROOT/llama.cpp}"
mkdir -p "$OUT"
c++ -std=c++17 -O2 -I "$SOURCE/include" -I "$SOURCE/ggml/include" \
  -I "$SOURCE/vendor/nlohmann" "$ROOT/scripts/capture_activations.cpp" \
  -L "$LIB" -Wl,-rpath,"$LIB" -lllama -lggml -lggml-base -o "$OUT/capture-activations"
printf '%s\n' "$OUT/capture-activations"
