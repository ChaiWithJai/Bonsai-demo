#!/bin/sh
set -eu
RESEARCH_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
RESEARCH_LIB="$RESEARCH_ROOT/prefill-campaign/research/fa-q32g2-isolated-20260916-0255/bin"
c++ -std=c++17 -O2 -I "$RESEARCH_ROOT/llama.cpp/include" -I "$RESEARCH_ROOT/llama.cpp/ggml/include" \
 -I "$RESEARCH_ROOT/llama.cpp/vendor/nlohmann" "$RESEARCH_ROOT/scripts/research/capture_pelican.cpp" \
 -L "$RESEARCH_LIB" -Wl,-rpath,"$RESEARCH_LIB" -lllama -lggml -lggml-base \
 -o "$RESEARCH_ROOT/.cache/bonsai/research-20260918/capture-pelican-hf-order"
