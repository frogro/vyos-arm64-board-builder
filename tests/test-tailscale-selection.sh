#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../lib/ui.sh
source "$ROOT/lib/ui.sh"

[[ "$(TAILSCALE_SUBNET_ROUTER=yes select_tailscale_subnet_router)" == "yes" ]]
[[ "$(TAILSCALE_SUBNET_ROUTER=true select_tailscale_subnet_router)" == "yes" ]]
[[ "$(TAILSCALE_SUBNET_ROUTER=no select_tailscale_subnet_router)" == "no" ]]
[[ "$(TAILSCALE_SUBNET_ROUTER=0 select_tailscale_subnet_router)" == "no" ]]

unset TAILSCALE_SUBNET_ROUTER
[[ "$(select_tailscale_subnet_router </dev/null)" == "no" ]]

if (TAILSCALE_SUBNET_ROUTER=invalid select_tailscale_subnet_router) >/dev/null 2>&1; then
    echo "ERROR: invalid Tailscale selection was accepted" >&2
    exit 1
fi

echo "PASS: Tailscale profile selection"
