#!/bin/bash
# tinyagentos rk-llama.cpp installer
# ---------------------------------------------------------------------------
# Downloads the pre-compiled rk-llama.cpp binary for RK3588 (Orange Pi 5+
# with the rknpu kernel driver) and installs it as a systemd unit. This is
# a second NPU backend alongside rkllama — useful for models that the
# rkllm-toolkit doesn't yet support (Gemma 4, Qwen 3.5+, etc).
#
# Requirements:
#   * RK3588 board (Orange Pi 5 / 5+ / 5 Max etc)
#   * librknnrt.so installed at /usr/lib/librknnrt.so (install-rknpu.sh
#     does this; running this script before that will fail)
#
# Environment overrides:
#   TAOS_RKLLAMACPP_DIR    install dir (default: ~<user>/rk-llama.cpp)
#   TAOS_RKLLAMACPP_PORT   server port (default: 8090)
#   TAOS_MIRROR_BASE       binary mirror (default: jaylfc/tinyagentos-rockchip-mirror on HF)
# ---------------------------------------------------------------------------
set -euo pipefail

log()  { echo -e "\033[1;34m[rkllamacpp]\033[0m $*"; }
warn() { echo -e "\033[1;33m[rkllamacpp]\033[0m $*" >&2; }
die()  { echo -e "\033[1;31m[rkllamacpp]\033[0m $*" >&2; exit 1; }

# -------- target user resolution -----------------------------------------
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    TARGET_USER="$SUDO_USER"
else
    TARGET_USER="$(id -un)"
fi
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
[[ -d "$TARGET_HOME" ]] || die "cannot resolve home for user $TARGET_USER"
TARGET_GROUP="$(id -gn "$TARGET_USER")"

INSTALL_DIR="${TAOS_RKLLAMACPP_DIR:-$TARGET_HOME/rk-llama.cpp}"
PORT="${TAOS_RKLLAMACPP_PORT:-8090}"
MIRROR_BASE="${TAOS_MIRROR_BASE:-https://huggingface.co/jaylfc/tinyagentos-rockchip-mirror/resolve/main}"
TARBALL_URL="${MIRROR_BASE}/binaries/rkllamacpp-aarch64-rk3588.tar.gz"

run_as_user() {
    if [[ "$(id -un)" == "$TARGET_USER" ]]; then
        "$@"
    else
        sudo -u "$TARGET_USER" -H "$@"
    fi
}

# -------- preflight ------------------------------------------------------

[[ "$(uname -m)" == "aarch64" ]] || die "this binary is aarch64-only (got $(uname -m))"
[[ -f /usr/lib/librknnrt.so ]] || die "librknnrt.so not found — run install-rknpu.sh first"

if [[ -r /proc/device-tree/compatible ]]; then
    if ! tr '\000' '\n' < /proc/device-tree/compatible | grep -qi 'rk3588'; then
        warn "this board's compatible string does not mention rk3588 — proceeding anyway"
    fi
fi

# -------- download + extract ---------------------------------------------

log "fetching rk-llama.cpp binary tarball"
log "  from: $TARBALL_URL"
log "  to:   $INSTALL_DIR"

run_as_user mkdir -p "$INSTALL_DIR/bin" "$INSTALL_DIR/models"

TMP_TAR="$(mktemp -t rkllamacpp.XXXXXX.tar.gz)"
curl -fSL --retry 3 --retry-delay 2 -o "$TMP_TAR" "$TARBALL_URL" \
    || die "download failed from $TARBALL_URL"

run_as_user tar xzf "$TMP_TAR" -C "$INSTALL_DIR" --strip-components=0 \
    || die "tar extraction failed"
rm -f "$TMP_TAR"

# Quick sanity check
[[ -x "$INSTALL_DIR/bin/llama-server" ]] || die "llama-server not present after extract"
[[ -x "$INSTALL_DIR/bin/llama-cli" ]] || die "llama-cli not present after extract"
log "binary layout:"
ls -la "$INSTALL_DIR/bin/" | grep -E "llama-(server|cli)|libggml-rknpu2" | head -5 || true

# -------- systemd unit ---------------------------------------------------

UNIT="/etc/systemd/system/rkllamacpp.service"
log "writing $UNIT"

# Note: the unit is intentionally not enabled at install time. It only
# starts once a model is registered (a GGUF placed at $INSTALL_DIR/models/active.gguf).
# The taOS RkLlamaCppInstaller flips on the unit after the first model install.

sudo tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=rk-llama.cpp NPU LLM server (taOS)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$TARGET_USER
Group=$TARGET_GROUP
WorkingDirectory=$INSTALL_DIR
Environment=LD_LIBRARY_PATH=$INSTALL_DIR/bin:/usr/lib
# RKNPU runtime opens many fd/handles per model layer; the default
# 1024 limit causes EMFILE during model load. 65536 is the same
# headroom the rkllama unit ends up using in practice.
LimitNOFILE=65536
# Free the port if a stale process is holding it (uncommon since we
# manage the unit, but cheap and matches rkllama.service).
ExecStartPre=-/bin/sh -c "/usr/bin/fuser -k -9 ${PORT}/tcp || true"
ExecStart=$INSTALL_DIR/bin/llama-server \\
    --model $INSTALL_DIR/models/active.gguf \\
    --host 0.0.0.0 \\
    --port $PORT \\
    --n-gpu-layers 99 \\
    --jinja
Restart=on-failure
RestartSec=10
KillMode=mixed
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
log "systemd unit installed (not started — waiting for first model)"

# -------- summary --------------------------------------------------------

cat <<EOF

  =================================================================
  rk-llama.cpp installed successfully
  =================================================================
    install dir:   $INSTALL_DIR
    binary:        $INSTALL_DIR/bin/llama-server
    models dir:    $INSTALL_DIR/models
    HTTP endpoint: http://localhost:$PORT (when started)
    systemd unit:  $UNIT (disabled until first model)

  Next steps:
    * Install a GGUF model from the taOS Store (e.g. Gemma 4 E2B,
      Qwen 3.5 2B). The first install will enable + start the unit.
    * Or manually: place a GGUF at $INSTALL_DIR/models/active.gguf
      and run: sudo systemctl enable --now rkllamacpp

  Differences from rkllama:
    * Uses GGUF format (downloaded from HF directly), not .rkllm
    * Architecture-agnostic — runs Gemma 4, Qwen 3.5+, etc that
      rkllama doesn't yet support
    * One model active at a time; switching means re-installing
EOF
