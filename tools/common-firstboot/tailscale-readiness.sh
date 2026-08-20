#!/usr/bin/env bash
# Read-only runtime audit. This script never installs, authenticates or
# configures Tailscale and never modifies the VyOS firewall.

set -u

failed=0

check_command()
{
    if command -v "$1" >/dev/null 2>&1; then
        printf 'PASS  command: %s\n' "$1"
    else
        printf 'FAIL  command missing: %s\n' "$1"
        failed=1
    fi
}

if [[ -c /dev/net/tun ]]; then
    printf 'PASS  TUN device: /dev/net/tun\n'
else
    printf 'FAIL  TUN device missing: /dev/net/tun\n'
    failed=1
fi

for command in curl ip nft sha256sum systemctl tar; do
    check_command "$command"
done

for setting in net.ipv4.ip_forward net.ipv6.conf.all.forwarding; do
    value="$(sysctl -n "$setting" 2>/dev/null || true)"
    if [[ "$value" == "1" ]]; then
        printf 'PASS  %s=1\n' "$setting"
    else
        printf 'WARN  %s=%s (enable through VyOS configuration)\n' \
            "$setting" "${value:-unknown}"
    fi
done

if findmnt -n --target /config >/dev/null 2>&1; then
    printf 'PASS  persistent configuration mount: /config\n'
else
    printf 'FAIL  persistent configuration mount missing: /config\n'
    failed=1
fi

if [[ -x /config/tailscale/bin/tailscaled ]]; then
    printf 'INFO  local tailscaled binary is installed\n'
else
    printf 'INFO  local tailscaled binary is not installed (expected initially)\n'
fi

exit "$failed"
