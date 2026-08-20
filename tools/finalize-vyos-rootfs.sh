#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: $0 <board> <rootfs>"

BOARD="${1:?$USAGE}"
ROOTFS="${2:?$USAGE}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$ROOT/tools/common-firstboot"

[[ -d "$ROOTFS" && -d "$PAYLOAD" ]] || {
    echo "ERROR: common VyOS rootfs input is incomplete" >&2
    exit 1
}

STAGE_DIR="$ROOTFS/usr/local/share/vyos-arm64-firstboot"
SBIN_DIR="$ROOTFS/usr/local/sbin"
UNIT_DIR="$ROOTFS/etc/systemd/system"
WANTS_DIR="$UNIT_DIR/timers.target.wants"

install -d -m 0755 "$STAGE_DIR" "$SBIN_DIR" "$UNIT_DIR" "$WANTS_DIR"

MULTI_USER_WANTS_DIR="$UNIT_DIR/multi-user.target.wants"
install -d -m 0755 "$MULTI_USER_WANTS_DIR"

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    install -m 0755 \
        "$PAYLOAD/$script" \
        "$STAGE_DIR/$script"
done

install \
    -m 0755 \
    "$PAYLOAD/vyos-arm64-dhcp-wan-firstboot-wrapper.sh" \
    "$SBIN_DIR/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"

install \
    -m 0755 \
    "$PAYLOAD/grow-persistence.sh" \
    "$SBIN_DIR/vyos-arm64-grow-persistence.sh"

install \
    -m 0755 \
    "$PAYLOAD/tailscale-readiness.sh" \
    "$SBIN_DIR/vyos-arm64-tailscale-readiness"

install \
    -m 0755 \
    "$PAYLOAD/tailscale-wrapper.sh" \
    "$SBIN_DIR/tailscale"

for unit in \
    vyos-arm64-dhcp-wan-firstboot.service \
    vyos-arm64-dhcp-wan-firstboot.timer
do
    install -m 0644 "$PAYLOAD/$unit" "$UNIT_DIR/$unit"
done

install -m 0644 \
    "$PAYLOAD/vyos-arm64-grow-persistence.service" \
    "$UNIT_DIR/vyos-arm64-grow-persistence.service"

install -m 0644 \
    "$PAYLOAD/vyos-arm64-tailscaled.service" \
    "$UNIT_DIR/vyos-arm64-tailscaled.service"

ln -sfn \
    ../vyos-arm64-dhcp-wan-firstboot.timer \
    "$WANTS_DIR/vyos-arm64-dhcp-wan-firstboot.timer"

ln -sfn \
    ../vyos-arm64-grow-persistence.service \
    "$MULTI_USER_WANTS_DIR/vyos-arm64-grow-persistence.service"

ln -sfn \
    ../vyos-arm64-tailscaled.service \
    "$MULTI_USER_WANTS_DIR/vyos-arm64-tailscaled.service"

echo "Installed common first-boot DHCP/SSH helpers for $BOARD"
