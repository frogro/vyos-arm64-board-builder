#!/usr/bin/env bash
set -euo pipefail

BINARY="/usr/libexec/tailscale/tailscale"
SOCKET="/run/tailscale/tailscaled.sock"

[[ -x "$BINARY" ]] || {
    echo "Tailscale is not installed in /usr/libexec/tailscale" >&2
    exit 127
}

exec "$BINARY" --socket="$SOCKET" "$@"
