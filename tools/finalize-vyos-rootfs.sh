#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: $0 <board> <rootfs> [tailscale yes|no] [network yes|no] [profile] [kvm yes|no] [kvm-provider] [capture-backend] [hid-capability]"

BOARD="${1:?$USAGE}"
ROOTFS="${2:?$USAGE}"
TAILSCALE_SUBNET_ROUTER="${3:-no}"
EXTENDED_NETWORK="${4:-no}"
BUILD_PROFILE="${5:-base}"
KVM_OVER_IP="${6:-no}"
KVM_HARDWARE_PROVIDER="${7:-disabled}"
KVM_CAPTURE_BACKEND="${8:-disabled}"
KVM_HID_GADGET="${9:-no}"

case "${TAILSCALE_SUBNET_ROUTER,,}" in
    1|true|yes|y|on|enabled) TAILSCALE_SUBNET_ROUTER=yes ;;
    0|false|no|n|off|disabled) TAILSCALE_SUBNET_ROUTER=no ;;
    *)
        echo "ERROR: invalid Tailscale profile value: $TAILSCALE_SUBNET_ROUTER" >&2
        exit 1
        ;;
esac

case "${KVM_OVER_IP,,}" in
    1|true|yes|y|on|enabled) KVM_OVER_IP=yes ;;
    0|false|no|n|off|disabled) KVM_OVER_IP=no ;;
    *) echo "ERROR: invalid KVM-over-IP value: $KVM_OVER_IP" >&2; exit 1 ;;
esac

case "${EXTENDED_NETWORK,,}" in
    1|true|yes|y|on|enabled) EXTENDED_NETWORK=yes ;;
    0|false|no|n|off|disabled) EXTENDED_NETWORK=no ;;
    *)
        echo "ERROR: invalid Extended Network value: $EXTENDED_NETWORK" >&2
        exit 1
        ;;
esac

[[ "$BUILD_PROFILE" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || {
    echo "ERROR: invalid build profile: $BUILD_PROFILE" >&2
    exit 1
}

for value in "$KVM_HARDWARE_PROVIDER" "$KVM_CAPTURE_BACKEND"; do
    [[ "$value" =~ ^[a-z0-9]+([+._-][a-z0-9]+)*$ ]] || {
        echo "ERROR: invalid KVM hardware metadata: $value" >&2
        exit 1
    }
done
[[ "$KVM_HID_GADGET" =~ ^(yes|no|runtime)$ ]] || {
    echo "ERROR: invalid KVM HID capability: $KVM_HID_GADGET" >&2
    exit 1
}

case "${EXTENDED_NETWORK}:${TAILSCALE_SUBNET_ROUTER}:${KVM_OVER_IP}" in
    no:no:no) EXPECTED_PROFILE=base ;;
    yes:no:no) EXPECTED_PROFILE=network ;;
    no:yes:no) EXPECTED_PROFILE=tailscale ;;
    yes:yes:no) EXPECTED_PROFILE=network-tailscale ;;
    no:no:yes) EXPECTED_PROFILE=kvm ;;
    yes:no:yes) EXPECTED_PROFILE=network-kvm ;;
    no:yes:yes) EXPECTED_PROFILE=tailscale-kvm ;;
    yes:yes:yes) EXPECTED_PROFILE=network-tailscale-kvm ;;
esac

[[ "$BUILD_PROFILE" == "$EXPECTED_PROFILE" ]] || {
    echo "ERROR: build profile '$BUILD_PROFILE' does not match selected features; expected '$EXPECTED_PROFILE'" >&2
    exit 1
}

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

PROFILE_DIR="$ROOTFS/usr/share/vyos-arm64-board-builder"
install -d -m 0755 "$PROFILE_DIR"
python3 - "$PROFILE_DIR/profile.json" "$BOARD" "$BUILD_PROFILE" \
    "$EXTENDED_NETWORK" "$TAILSCALE_SUBNET_ROUTER" "$KVM_OVER_IP" \
    "$KVM_HARDWARE_PROVIDER" "$KVM_CAPTURE_BACKEND" "$KVM_HID_GADGET" <<'PY'
import json
from pathlib import Path
import sys

output, board, profile, network, tailscale, kvm, provider, capture, hid = sys.argv[1:]
Path(output).write_text(json.dumps({
    "schema": 2,
    "architecture": "arm64",
    "board": board,
    "profile": profile,
    "features": {
        "extended_network": network == "yes",
        "tailscale_subnet_router": tailscale == "yes",
        "kvm_over_ip": kvm == "yes",
    },
    "kvm": {
        "hardware_provider": provider,
        "capture_backend": capture,
        "hid_gadget": hid,
    },
}, indent=2) + "\n")
PY

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

if [[ "$TAILSCALE_SUBNET_ROUTER" == "yes" ]]; then
    install -m 0755 \
        "$PAYLOAD/tailscale-readiness.sh" \
        "$SBIN_DIR/vyos-arm64-tailscale-readiness"

    install -m 0755 \
        "$PAYLOAD/tailscale-wrapper.sh" \
        "$SBIN_DIR/tailscale"
fi

if [[ "$KVM_OVER_IP" == "yes" ]]; then
    install -m 0755 \
        "$PAYLOAD/kvm-over-ip-readiness.sh" \
        "$SBIN_DIR/vyos-arm64-kvm-readiness"
    install -d -m 0750 "$ROOTFS/config/kvm-over-ip"
fi

for unit in \
    vyos-arm64-dhcp-wan-firstboot.service \
    vyos-arm64-dhcp-wan-firstboot.timer
do
    install -m 0644 "$PAYLOAD/$unit" "$UNIT_DIR/$unit"
done

install -m 0644 \
    "$PAYLOAD/vyos-arm64-grow-persistence.service" \
    "$UNIT_DIR/vyos-arm64-grow-persistence.service"

if [[ "$TAILSCALE_SUBNET_ROUTER" == "yes" ]]; then
    install -m 0644 \
        "$PAYLOAD/vyos-arm64-tailscaled.service" \
        "$UNIT_DIR/vyos-arm64-tailscaled.service"
fi

ln -sfn \
    ../vyos-arm64-dhcp-wan-firstboot.timer \
    "$WANTS_DIR/vyos-arm64-dhcp-wan-firstboot.timer"

ln -sfn \
    ../vyos-arm64-grow-persistence.service \
    "$MULTI_USER_WANTS_DIR/vyos-arm64-grow-persistence.service"

if [[ "$TAILSCALE_SUBNET_ROUTER" == "yes" ]]; then
    ln -sfn \
        ../vyos-arm64-tailscaled.service \
        "$MULTI_USER_WANTS_DIR/vyos-arm64-tailscaled.service"
fi

echo "Installed common first-boot DHCP/SSH helpers for $BOARD"
