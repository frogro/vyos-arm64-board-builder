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

PASSWD_FILE="$ROOTFS/etc/passwd"

[[ -r "$PASSWD_FILE" ]] || {
    echo "ERROR: VyOS passwd database is missing: $PASSWD_FILE" >&2
    exit 1
}

VYOS_UID="$(awk -F: '$1 == "vyos" { print $3; exit }' "$PASSWD_FILE")"
VYOS_GID="$(awk -F: '$1 == "vyos" { print $4; exit }' "$PASSWD_FILE")"

[[ "$VYOS_UID" =~ ^[0-9]+$ && "$VYOS_GID" =~ ^[0-9]+$ ]] || {
    echo "ERROR: unable to resolve the vyos user in $PASSWD_FILE" >&2
    exit 1
}

HOME_DIR="$ROOTFS/home/vyos"
SBIN_DIR="$ROOTFS/usr/local/sbin"
UNIT_DIR="$ROOTFS/etc/systemd/system"
WANTS_DIR="$UNIT_DIR/timers.target.wants"

install -d -m 0755 -o "$VYOS_UID" -g "$VYOS_GID" "$HOME_DIR"
install -d -m 0755 "$SBIN_DIR" "$UNIT_DIR" "$WANTS_DIR"

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    install \
        -m 0755 \
        -o "$VYOS_UID" \
        -g "$VYOS_GID" \
        "$PAYLOAD/$script" \
        "$HOME_DIR/$script"
done

install \
    -m 0755 \
    "$PAYLOAD/vyos-arm64-dhcp-wan-firstboot-wrapper.sh" \
    "$SBIN_DIR/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"

for unit in \
    vyos-arm64-dhcp-wan-firstboot.service \
    vyos-arm64-dhcp-wan-firstboot.timer
do
    install -m 0644 "$PAYLOAD/$unit" "$UNIT_DIR/$unit"
done

ln -sfn \
    ../vyos-arm64-dhcp-wan-firstboot.timer \
    "$WANTS_DIR/vyos-arm64-dhcp-wan-firstboot.timer"

echo "Installed common first-boot DHCP/SSH helpers for $BOARD"
