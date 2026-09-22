#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

SYS_CLASS_BLOCK="$WORK/sys/class/block"
SYS_DEVICES="$WORK/sys/devices/virtual/block"
mkdir -p "$SYS_CLASS_BLOCK" "$SYS_DEVICES"

add_disk()
{
    local disk="$1"
    shift
    local partition
    local number

    mkdir -p "$SYS_DEVICES/$disk"
    ln -s "$SYS_DEVICES/$disk" "$SYS_CLASS_BLOCK/$disk"

    while (( $# )); do
        partition="$1"
        number="$2"
        shift 2
        mkdir -p "$SYS_DEVICES/$disk/$partition"
        printf '%s\n' "$number" > "$SYS_DEVICES/$disk/$partition/partition"
        printf '%s\n' 542720 > "$SYS_DEVICES/$disk/$partition/start"
        ln -s "$SYS_DEVICES/$disk/$partition" "$SYS_CLASS_BLOCK/$partition"
    done
}

add_disk mmcblk1 mmcblk1p1 1 mmcblk1p2 2 mmcblk1p3 3
add_disk nvme0n1 nvme0n1p1 1 nvme0n1p3 3
add_disk sda sda1 1 sda2 2 sda3 3

# shellcheck disable=SC1091
source "$ROOT/tools/common-firstboot/grow-persistence.sh"

[[ "$(resolve_partition /dev/mmcblk1p3)" == "mmcblk1 3" ]]
[[ "$(resolve_partition /dev/nvme0n1p3)" == "nvme0n1 3" ]]
[[ "$(resolve_partition /dev/sda3)" == "sda 3" ]]

[[ "$(last_partition_number mmcblk1)" == "3" ]]
[[ "$(last_partition_number nvme0n1)" == "3" ]]
[[ "$(last_partition_number sda)" == "3" ]]

if resolve_partition /dev/mmcblk1 >/dev/null 2>&1; then
    echo "ERROR: whole disk was accepted as a partition" >&2
    exit 1
fi

grep -Fq 'parted ---pretend-input-tty' \
    "$ROOT/tools/common-firstboot/grow-persistence.sh"

if grep -Eq 'lsblk .*\b(PARTN|PKNAME|FSTYPE|START)\b' \
    "$ROOT/tools/common-firstboot/grow-persistence.sh"
then
    echo "ERROR: resolver still relies on optional lsblk columns" >&2
    exit 1
fi

echo "PASS: generic persistence partition resolver"
