#!/usr/bin/env bash
set -euo pipefail

BINARY="/config/tailscale/bin/tailscale"
SOCKET="/run/tailscale/tailscaled.sock"

[[ -x "$BINARY" ]] || {
    echo "Tailscale is not installed in /config/tailscale/bin" >&2
    exit 127
}

exec "$BINARY" --socket="$SOCKET" "$@"
