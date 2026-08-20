#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: $0 <board> <rootfs> <network-artifacts>"

BOARD="${1:?$USAGE}"
ROOTFS="${2:?$USAGE}"
ARTIFACTS="${3:?$USAGE}"

[[ -d "$ROOTFS" ]] || {
    echo "ERROR: VyOS rootfs missing: $ROOTFS" >&2
    exit 1
}

[[ -d "$ARTIFACTS" ]] || {
    echo "ERROR: network artifact directory missing: $ARTIFACTS" >&2
    exit 1
}

if [[ -d "$ARTIFACTS/root" ]]; then
    rsync \
        -aH \
        --numeric-ids \
        "$ARTIFACTS/root/" \
        "$ROOTFS/"
fi

DOC="$ROOTFS/usr/share/doc/vyos-arm64-board-builder/network"
install -d -m 0755 "$DOC"

for report in \
    extended-network-report.txt \
    extended-network-kconfig-report.txt \
    extended-network-kconfig-report.json \
    network-firmware-manifest.json \
    required-firmware.txt \
    required-firmware-baseline.txt \
    required-firmware-extended.txt \
    installed-firmware.txt \
    missing-firmware.txt
do
    [[ -f "$ARTIFACTS/$report" ]] || continue
    install -m 0644 "$ARTIFACTS/$report" "$DOC/$report"
done

echo "Installed network firmware and reports for $BOARD"
