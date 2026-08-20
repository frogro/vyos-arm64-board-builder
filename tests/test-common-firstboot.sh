#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ROOTFS="$WORK/rootfs"
mkdir -p "$ROOTFS/etc"

printf 'vyos:x:%s:%s:VyOS user:/home/vyos:/bin/vbash\n' \
    "$(id -u)" \
    "$(id -g)" \
    > "$ROOTFS/etc/passwd"

bash "$ROOT/tools/finalize-vyos-rootfs.sh" test-board "$ROOTFS"

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    test -x "$ROOTFS/home/vyos/$script"
done

test -x "$ROOTFS/usr/local/sbin/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.service"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.timer"
test -L "$ROOTFS/etc/systemd/system/timers.target.wants/vyos-arm64-dhcp-wan-firstboot.timer"

grep -Fq 'SSID="${SSID:-VyOS-AP}"' \
    "$ROOTFS/home/vyos/ap-dhcp-wan-setup.sh"
grep -Fq 'PASSPHRASE="${PASSPHRASE:-vyosvyos}"' \
    "$ROOTFS/home/vyos/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$ROOTFS/home/vyos/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$ROOTFS/home/vyos/modem-connect.sh"

if grep -RqiE \
    'frogro/vyos-build-pi5|set system update-check|UPDATE_CHECK_URL|Photobooth|PHOTOBOOTH' \
    "$ROOTFS/home/vyos" \
    "$ROOTFS/usr/local/sbin" \
    "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot."*
then
    echo "ERROR: board-specific branding or update channel remains" >&2
    exit 1
fi

echo "PASS: common ARM64 first-boot rootfs contract"
