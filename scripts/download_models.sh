#!/bin/sh
# Download Bonsai / Ternary-Bonsai models from HuggingFace.
#
# Usage:
#   ./scripts/download_models.sh                                         # Bonsai 2 27B (default)
#   BONSAI_MODEL=4B ./scripts/download_models.sh                         # Ternary-Bonsai 4B
#   BONSAI_FAMILY=bonsai ./scripts/download_models.sh                    # Bonsai (1-bit) 27B
#   BONSAI_FAMILY=ternary BONSAI_MODEL=1.7B ./scripts/download_models.sh # Ternary-Bonsai 1.7B
#   BONSAI_MODEL=all ./scripts/download_models.sh                        # All sizes of the selected family
#   BONSAI_FAMILY=all ./scripts/download_models.sh                       # Both families, 27B size
#   BONSAI_FAMILY=all BONSAI_MODEL=all ./scripts/download_models.sh      # Full matrix (8 downloads)
#   BONSAI_SKIP_GGUF=1 ./scripts/download_models.sh                      # MLX only (macOS) — saves disk space
#   BONSAI_MODELS_PLAN=1 ./scripts/download_models.sh                    # Preview reuse/downloads; no weights downloaded
#   BONSAI_DOWNLOAD_DRAFTER=1 ./scripts/download_models.sh               # Include experimental DSpark sidecar
#
# Set BONSAI_TOKEN (a read-only HF token) if you need to pull a repo that is
# still private; public repos download anonymously with no token.
#
# Set BONSAI_SKIP_GGUF=1 to skip the GGUF download entirely (llama.cpp backend
# won't be usable afterwards — only makes sense if you only run the MLX
# backend on Apple Silicon). Set BONSAI_SKIP_MLX=1 for the inverse.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
. "$SCRIPT_DIR/common.sh"
assert_valid_model
DEMO_DIR="$(resolve_demo_dir)"
cd "$DEMO_DIR"

VENV_PY="$DEMO_DIR/.venv/bin/python"

# ── HuggingFace auth ──
# Use BONSAI_TOKEN (env, or the gitignored .bonsai_token file) if present.
# It is only needed for a repo that is still private; public repos download
# anonymously. We never hard-skip on a missing token: HF surfaces a clear 401
# if a repo genuinely needs auth, and once a repo goes public no token is
# required at all.
if [ -z "$BONSAI_TOKEN" ] && [ -f "$DEMO_DIR/.bonsai_token" ]; then
    BONSAI_TOKEN="$(tr -d '\r\n' < "$DEMO_DIR/.bonsai_token")"
fi
# Offer (never require) an interactive prompt when a tty is attached and no
# token is set. Declining is fine. `|| true`: EOF must not abort under set -e.
if [ -z "$BONSAI_TOKEN" ] && [ -r /dev/tty ]; then
    printf "  Optional HuggingFace token for any still-private repo (press Enter to skip): "
    { read -r BONSAI_TOKEN </dev/tty; } 2>/dev/null || true
fi
if [ -n "$BONSAI_TOKEN" ]; then
    export BONSAI_TOKEN
    export HF_TOKEN="$BONSAI_TOKEN"
fi

# ── Find Python with huggingface_hub ──
PY=""
if [ -x "$VENV_PY" ]; then
    PY="$VENV_PY"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
fi

if [ -z "$PY" ] || ! "$PY" -c "import huggingface_hub" 2>/dev/null; then
    err "huggingface_hub not found."
    echo "  Run ./setup.sh first, or: uv pip install huggingface-hub"
    exit 1
fi

# ── Helper: download a HF repo via Python ──
# Third arg (optional) is a comma-separated allow_patterns filter — when set,
# only files matching any of those glob patterns are downloaded.
hf_download() {
    _repo="$1"
    _dest="$2"
    _patterns="${3:-}"
    if [ "${BONSAI_MODELS_PLAN:-0}" = "1" ]; then
        "$PY" "$SCRIPT_DIR/model_store.py" "$_repo" "$_dest" --patterns "$_patterns" --plan
    else
        "$PY" "$SCRIPT_DIR/model_store.py" "$_repo" "$_dest" --patterns "$_patterns"
    fi
}

# Unlike `ls`, this rejects dangling symlinks and zero-byte interrupted files.
model_file_present() {
    for _model_file in "$1"/$2; do
        [ -f "$_model_file" ] && [ -s "$_model_file" ] && return 0
    done
    return 1
}

# ── Download GGUF + MLX for one (family, size) pair ──
download_one() {
    _family="$1"
    _size="$2"
    # Each GGUF repo ships multiple quants (e.g. F16 + Q2_0); we only want the
    # quant the demo is built around, so restrict the download via allow_patterns.
    case "$_family" in
        bonsai2)
            # Every Bonsai 2 band needs the fork's kernels, so there is no mainline-compatible
            # variant to choose between: the PQ2_0 band plus the projector.
            bonsai2_size_available "$_size" || { info "Bonsai 2 is 27B; skipping ${_size}."; return 0; }
            _gguf_repo="prism-ml/Ternary-Bonsai-2-${_size}-gguf"
            _mlx_repo="prism-ml/Ternary-Bonsai-2-${_size}-mlx-2bit"
            _gguf_dir="models/bonsai2-gguf/${_size}"
            _mlx_dir="models/Ternary-Bonsai-2-${_size}-mlx-2bit"
            _display="Bonsai-2-${_size}"
            _gguf_pattern="*-PQ2_0.gguf"
            ;;
        bonsai)
            _gguf_repo="prism-ml/Bonsai-${_size}-gguf"
            _mlx_repo="prism-ml/Bonsai-${_size}-mlx-1bit"
            _gguf_dir="models/gguf/${_size}"
            _mlx_dir="models/Bonsai-${_size}-mlx"
            _display="Bonsai-${_size}"
            _gguf_pattern="*-Q1_0.gguf"
            ;;
        ternary)
            _gguf_repo="prism-ml/Ternary-Bonsai-${_size}-gguf"
            _mlx_repo="prism-ml/Ternary-Bonsai-${_size}-mlx-2bit"
            _gguf_dir="models/ternary-gguf/${_size}"
            _mlx_dir="models/Ternary-Bonsai-${_size}-mlx-2bit"
            _display="Ternary-Bonsai-${_size}"
            # ternary: download only the format the installed backend will use
            # (PQ2_0 where it has kernels, official group-64 otherwise; both when no
            # binary is installed yet). See select_model_gguf in common.sh and
            # MODEL-FORMATS.md. Newer repos ship the official file as plain
            # *-Q2_0.gguf; download_one falls back to that name when no *g64 exists.
            _dl_backend=""
            for _bd in bin/mac bin/cuda bin/rocm bin/hip bin/vulkan bin/cpu; do
                [ -d "$_bd" ] && _dl_backend="${_bd#bin/}" && break
            done
            if [ -z "$_dl_backend" ]; then
                _gguf_pattern="*-PQ2_0.gguf,*g64.gguf"
            elif pq2_0_ready_backend "$_dl_backend"; then
                _gguf_pattern="*-PQ2_0.gguf"
            else
                _gguf_pattern="*g64.gguf"
            fi
            ;;
    esac

    # 27B extras: the mmproj (multimodal projector) for image input, and the
    # paired dspark drafter only when explicitly requested. The resolver keeps
    # one installed projector or selects BF16, rather than downloading both.
    _dl_patterns="$_gguf_pattern"
    _mmproj_pattern=""
    _drafter_pattern=""
    if [ "$_family" = "bonsai2" ]; then
        # Reuse the verified BF16 projector if already installed; no Bonsai 2 drafter.
        _mmproj_pattern="*mmproj*.gguf"
        _dl_patterns="$_gguf_pattern,$_mmproj_pattern"
    elif [ "$_size" = "27B" ]; then
        _mmproj_pattern="*mmproj*.gguf"
        # the bf16 drafter is the input for the one-time gguf-dspark-to-dflash
        # conversion (see SPECULATIVE.md); the legacy Q4_1 sidecar cannot load on v7
        if [ "${BONSAI_DOWNLOAD_DRAFTER:-${BONSAI_SPECULATIVE:-0}}" = "1" ]; then
            _drafter_pattern="*dspark-bf16*.gguf"
        fi
        _dl_patterns="$_gguf_pattern,$_mmproj_pattern"
        [ -z "$_drafter_pattern" ] || _dl_patterns="$_dl_patterns,$_drafter_pattern"
    fi

    # GGUF — stderr flows to the user so auth/network errors are visible.
    # Fast-path and post-download checks both filter on the target quant pattern
    # (not just any *.gguf) so a leftover F16 or other quant from an earlier
    # download doesn't get picked up at runtime. For 27B the fast-path also
    # requires a projector and, only when opted in, the speculative drafter.
    if bonsai_should_skip_gguf; then
        info "Skipping GGUF ${_display} (BONSAI_SKIP_GGUF=1)."
    else
        _gguf_present=false
        _gguf_check_pattern="$(printf '%s' "$_gguf_pattern" | tr ',' ' ')"
        _gguf_any_present() {
            for _p in $_gguf_check_pattern; do
                model_file_present "$_gguf_dir" "$_p" && return 0
            done
            # a previous run that fell back to the plain official name marked the dir
            [ -f "$_gguf_dir/.official-q2_0" ] && model_file_present "$_gguf_dir" "*-Q2_0.gguf" && return 0
            return 1
        }
        if [ -d "$_gguf_dir" ] && _gguf_any_present; then
            if { [ -z "$_mmproj_pattern" ] || model_file_present "$_gguf_dir" "$_mmproj_pattern"; } \
                && { [ -z "$_drafter_pattern" ] || model_file_present "$_gguf_dir" "$_drafter_pattern"; }; then
                _gguf_present=true
            fi
        fi
        if [ "${BONSAI_MODELS_PLAN:-0}" = "1" ]; then
            hf_download "$_gguf_repo" "$_gguf_dir" "$_dl_patterns"
        elif [ "$_gguf_present" = true ] && [ -z "${BONSAI_MODEL_REVISION:-}" ]; then
            info "GGUF ${_display} (${_gguf_pattern}) already present in ${_gguf_dir}/"
        else
            step "Resolving GGUF ${_display}: reuse verified local files, download only missing files ..."
            mkdir -p "$_gguf_dir"
            if ! hf_download "$_gguf_repo" "$_gguf_dir" "$_dl_patterns"; then
                err "Failed to download GGUF ${_display} from ${_gguf_repo}."
                exit 1
            fi
            if ! _gguf_any_present; then
                # newer repos ship the official group-64 file as plain *-Q2_0.gguf
                # and carry no *g64 name; fall back to that exact pattern.
                step "No PQ2_0/g64 file in ${_gguf_repo}; falling back to *-Q2_0.gguf (official group-64 on current repos) ..."
                if ! hf_download "$_gguf_repo" "$_gguf_dir" "*-Q2_0.gguf" || ! ls "$_gguf_dir"/*-Q2_0.gguf >/dev/null 2>&1; then
                    err "Download reported success but no usable model file was written to ${_gguf_dir}/."
                    exit 1
                fi
                # mark the dir: its plain-named Q2_0 is the OFFICIAL group-64 file, so
                # the selector and the presence fast-path may trust that name here
                touch "$_gguf_dir/.official-q2_0"
            fi
            if [ -n "$_mmproj_pattern" ] && ! ls "$_gguf_dir"/$_mmproj_pattern >/dev/null 2>&1; then
                warn "No ${_mmproj_pattern} file in ${_gguf_repo} — image input will be disabled for ${_display}."
            fi
            if [ -n "$_drafter_pattern" ] && ! ls "$_gguf_dir"/$_drafter_pattern >/dev/null 2>&1; then
                warn "No ${_drafter_pattern} file in ${_gguf_repo}; speculative decoding (BONSAI_SPECULATIVE=1) will be unavailable for ${_display}."
            fi
            info "GGUF ${_display} downloaded to ${_gguf_dir}/"
        fi
    fi

    # MLX (macOS Apple Silicon only; skipped on Intel or when BONSAI_SKIP_MLX=1)
    if [ "$(uname -s)" = "Darwin" ] && ! bonsai_should_skip_mlx; then
        if [ "${BONSAI_MODELS_PLAN:-0}" = "1" ]; then
            hf_download "$_mlx_repo" "$_mlx_dir"
        else
            step "Resolving MLX ${_display}: verify all files, reuse before download ..."
            hf_download "$_mlx_repo" "$_mlx_dir"
            info "MLX ${_display} downloaded to ${_mlx_dir}/"
        fi
    fi
}

[ "${BONSAI_MODELS_PLAN:-0}" = "1" ] || mkdir -p models

# Expand "all" for family and size into concrete lists, then iterate.
case "$BONSAI_FAMILY" in
    all) _families="bonsai2 bonsai ternary" ;;
    *)   _families="$BONSAI_FAMILY" ;;
esac
case "$BONSAI_MODEL" in
    all) _sizes="27B 8B 4B 1.7B" ;;
    *)   _sizes="$BONSAI_MODEL" ;;
esac

for _f in $_families; do
    for _s in $_sizes; do
        download_one "$_f" "$_s"
    done
done

if [ "$(uname -s)" != "Darwin" ]; then
    info "Skipping MLX models (macOS only)."
elif bonsai_should_skip_mlx; then
    info "Skipping MLX weights (Intel macOS or BONSAI_SKIP_MLX=1)."
fi

echo ""
if [ "${BONSAI_MODELS_PLAN:-0}" = "1" ]; then
    info "Model plan complete — no weights downloaded or linked."
else
    info "Model setup complete."
fi
