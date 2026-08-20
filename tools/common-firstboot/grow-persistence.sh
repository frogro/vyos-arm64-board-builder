#!/bin/bash
# Grow the last VyOS persistence partition and its ext4 filesystem to the
# installed medium. This is intentionally based on the mounted persistence
# device rather than a board-specific /dev path.

set -u

MARKER="/config/.vyos-arm64-persistence-grown"
MOUNTPOINT="/usr/lib/live/mount/persistence"

log()
{
    printf '%s %s\n' "$(date -Is)" "vyos-arm64-grow-persistence: $*"
}

[[ -e "$MARKER" ]] && exit 0

for cmd in \
    awk \
    blockdev \
    findmnt \
    lsblk \
    parted \
    partprobe \
    partx \
    readlink \
    resize2fs \
    udevadm
do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        log "required command missing: $cmd"
        exit 1
    fi
done

SOURCE="$(findmnt -n -o SOURCE --target "$MOUNTPOINT" 2>/dev/null || true)"
SOURCE="${SOURCE%%[*}"
SOURCE="$(readlink -f "$SOURCE" 2>/dev/null || true)"

[[ -b "$SOURCE" ]] || {
    log "unable to resolve persistence block device from $MOUNTPOINT"
    exit 1
}

PARENT="$(lsblk -dnro PKNAME "$SOURCE" 2>/dev/null || true)"
PARTITION_NUMBER="$(lsblk -dnro PARTN "$SOURCE" 2>/dev/null || true)"
FILESYSTEM_TYPE="$(lsblk -dnro FSTYPE "$SOURCE" 2>/dev/null || true)"

[[ -n "$PARENT" && "$PARTITION_NUMBER" =~ ^[0-9]+$ ]] || {
    log "persistence source is not a resolvable partition: $SOURCE"
    exit 1
}

[[ "$FILESYSTEM_TYPE" == "ext4" ]] || {
    log "unsupported persistence filesystem: $FILESYSTEM_TYPE"
    exit 1
}

DISK="/dev/$PARENT"
LAST_PARTITION_NUMBER="$(
    lsblk -lnro PARTN "$DISK" |
        awk 'NF { last = $1 } END { print last }'
)"

[[ "$PARTITION_NUMBER" == "$LAST_PARTITION_NUMBER" ]] || {
    log "refusing to grow non-final partition $SOURCE"
    exit 1
}

BEFORE_BYTES="$(blockdev --getsize64 "$SOURCE")"
DISK_SECTORS="$(blockdev --getsz "$DISK")"
PARTITION_START_SECTORS="$(lsblk -dnro START "$SOURCE")"
PARTITION_SECTORS="$(blockdev --getsz "$SOURCE")"
FREE_TAIL_SECTORS=$((
    DISK_SECTORS - PARTITION_START_SECTORS - PARTITION_SECTORS
))

# A small GPT trailer/alignment gap is normal. Avoid rewriting an already
# expanded table on every system-image boot.
if (( FREE_TAIL_SECTORS < 65536 )); then
    resize2fs "$SOURCE"
    touch "$MARKER"
    chmod 600 "$MARKER"
    log "persistence already spans the medium"
    exit 0
fi

log "expanding partition $SOURCE on $DISK"

parted --script --fix "$DISK" print >/dev/null
printf 'Yes\n' |
    parted ---pretend-input-tty "$DISK" \
        resizepart "$PARTITION_NUMBER" 100%

partprobe "$DISK" || true
partx --update --nr "$PARTITION_NUMBER" "$DISK" || true
udevadm settle || true

AFTER_BYTES="$(blockdev --getsize64 "$SOURCE")"

if (( AFTER_BYTES <= BEFORE_BYTES )); then
    log "partition table expanded; kernel will retry after the next reboot"
    exit 0
fi

resize2fs "$SOURCE"

touch "$MARKER"
chmod 600 "$MARKER"
log "expanded persistence from $BEFORE_BYTES to $AFTER_BYTES bytes"
