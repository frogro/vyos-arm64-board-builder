#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

ROOTFS="$WORK/rootfs"
mkdir -p "$ROOTFS"

STAGE="$ROOTFS/usr/local/share/vyos-arm64-firstboot"

bash "$ROOT/tools/finalize-vyos-rootfs.sh" test-board "$ROOTFS" no

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    test -x "$STAGE/$script"
done

test -x "$ROOTFS/usr/local/sbin/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"
test -x "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
test ! -e "$ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"
test ! -e "$ROOTFS/usr/local/sbin/tailscale"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.service"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.timer"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-grow-persistence.service"
test ! -e "$ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
test -L "$ROOTFS/etc/systemd/system/timers.target.wants/vyos-arm64-dhcp-wan-firstboot.timer"
test -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-grow-persistence.service"
test ! -e "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-tailscaled.service"

TAILSCALE_ROOTFS="$WORK/tailscale-rootfs"
mkdir -p "$TAILSCALE_ROOTFS"
bash "$ROOT/tools/finalize-vyos-rootfs.sh" test-board "$TAILSCALE_ROOTFS" yes

test -x "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"
test -x "$TAILSCALE_ROOTFS/usr/local/sbin/tailscale"
test -f "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
test -L "$TAILSCALE_ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-tailscaled.service"

grep -Fq 'ConditionFileIsExecutable=/config/tailscale/bin/tailscaled' \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
grep -Fq -- '--state=/config/tailscale/state/tailscaled.state' \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
grep -Fq 'Read-only runtime audit' \
    "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"

grep -Fq '/usr/lib/live/mount/persistence' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'resizepart "$PARTITION_NUMBER" 100%' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'resize2fs "$SOURCE"' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq '"$device_sysfs/partition"' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'findmnt -n -o FSTYPE' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"

grep -Fq 'SSID="${SSID:-VyOS-AP}"' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq 'PASSPHRASE="${PASSPHRASE:-vyosvyos}"' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$STAGE/modem-connect.sh"

if grep -RqiE \
    'frogro/vyos-build-pi5|set system update-check|UPDATE_CHECK_URL|Photobooth|PHOTOBOOTH' \
    "$STAGE" \
    "$ROOTFS/usr/local/sbin" \
    "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot."*
then
    echo "ERROR: board-specific branding or update channel remains" >&2
    exit 1
fi

if grep -qiE \
    'authkey|192\.168\.|10\.3\.|--advertise-routes' \
    "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness" \
    "$TAILSCALE_ROOTFS/usr/local/sbin/tailscale" \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
then
    echo "ERROR: Tailscale preparation contains identity or route policy" >&2
    exit 1
fi

echo "PASS: common ARM64 first-boot rootfs contract"
