#!/bin/bash
# Grow the last VyOS persistence partition and its ext4 filesystem to the
# installed medium. This is intentionally based on the mounted persistence
# device rather than a board-specific /dev path.

set -u

MARKER="/config/.vyos-arm64-persistence-grown"
MOUNTPOINT="/usr/lib/live/mount/persistence"
SYS_CLASS_BLOCK="${SYS_CLASS_BLOCK:-/sys/class/block}"

log()
{
    printf '%s %s\n' "$(date -Is)" "vyos-arm64-grow-persistence: $*"
}

resolve_partition()
{
    local source="$1"
    local device_name
    local device_sysfs
    local parent_name
    local partition_number

    device_name="$(basename "$source")"
    device_sysfs="$SYS_CLASS_BLOCK/$device_name"

    [[ -r "$device_sysfs/partition" ]] || return 1

    partition_number="$(cat "$device_sysfs/partition")"
    [[ "$partition_number" =~ ^[0-9]+$ ]] || return 1

    parent_name="$(
        basename "$(dirname "$(readlink -f "$device_sysfs")")"
    )"
    [[ -n "$parent_name" && "$parent_name" != "$device_name" ]] || return 1

    printf '%s %s\n' "$parent_name" "$partition_number"
}

last_partition_number()
{
    local parent_name="$1"
    local candidate
    local candidate_parent
    local candidate_number
    local last=0

    for candidate in "$SYS_CLASS_BLOCK"/*; do
        [[ -r "$candidate/partition" ]] || continue
        candidate_parent="$(
            basename "$(dirname "$(readlink -f "$candidate")")"
        )"
        [[ "$candidate_parent" == "$parent_name" ]] || continue

        candidate_number="$(cat "$candidate/partition")"
        [[ "$candidate_number" =~ ^[0-9]+$ ]] || continue
        (( candidate_number > last )) && last="$candidate_number"
    done

    (( last > 0 )) || return 1
    printf '%s\n' "$last"
}

main()
{
[[ -e "$MARKER" ]] && exit 0

for cmd in \
    blockdev \
    findmnt \
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

PARTITION_IDENTITY="$(resolve_partition "$SOURCE" 2>/dev/null || true)"
read -r PARENT PARTITION_NUMBER <<< "$PARTITION_IDENTITY"
FILESYSTEM_TYPE="$(
    findmnt -n -o FSTYPE --target "$MOUNTPOINT" 2>/dev/null || true
)"

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
    last_partition_number "$PARENT" 2>/dev/null || true
)"

[[ "$PARTITION_NUMBER" == "$LAST_PARTITION_NUMBER" ]] || {
    log "refusing to grow non-final partition $SOURCE"
    exit 1
}

BEFORE_BYTES="$(blockdev --getsize64 "$SOURCE")"
DISK_SECTORS="$(blockdev --getsz "$DISK")"
PARTITION_START_SECTORS="$(cat "$SYS_CLASS_BLOCK/$(basename "$SOURCE")/start")"
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
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    main "$@"
fi
