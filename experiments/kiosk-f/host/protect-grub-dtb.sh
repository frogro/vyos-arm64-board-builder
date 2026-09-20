#!/bin/bash
# Explicit experimental F staging, on live host or offline rootfs as root.
set -euo pipefail
ROOTFS=${1:?rootfs required}
DTB=${2:?relative board dtb required}
SOURCE=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
TEMPLATE=/usr/share/vyos/templates/grub/grub_vyos_version.j2
DIVERT=${TEMPLATE}.vyarm-upstream
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/usr/share/vyos/templates/grub"
EXISTING=$(dpkg-divert --root "$ROOTFS" --listpackage "$TEMPLATE")
if [[ -n "$EXISTING" && "$EXISTING" != LOCAL ]]; then
    echo 'Refusing foreign template diversion' >&2; exit 1
fi
if [[ -n "$EXISTING" ]]; then
    [[ $(dpkg-divert --root "$ROOTFS" --truename "$TEMPLATE") == "$DIVERT" ]] || exit 1
    cp "$ROOTFS$DIVERT" "$WORK$TEMPLATE"
else
    [[ ! -e "$ROOTFS$DIVERT" ]] || exit 1
    cp "$ROOTFS$TEMPLATE" "$WORK$TEMPLATE"
fi
# Validate and patch before altering the live template or diversion database.
python3 "$SOURCE/tools/patch-vyos-grub-board-dtb.py" "$WORK" "$DTB"
if [[ -z "$EXISTING" ]]; then
    dpkg-divert --root "$ROOTFS" --local --add --rename --divert "$DIVERT" "$TEMPLATE"
fi
install -m 644 "$WORK$TEMPLATE" "$ROOTFS$TEMPLATE"
