#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARMBIAN="${ARMBIAN:-$ROOT/cache/armbian-build}"

BOARD="${1:?Usage: $0 <board> [branch] [output-dir]}"
BRANCH="${2:-current}"
OUT="${3:-$ROOT/work/build/$BOARD/armbian-effective}"

RAW="$OUT/config-dump.raw"
LOG="$OUT/config-dump.stderr.log"
JSON="$OUT/config-dump.json"
ENVFILE="$OUT/config.env"

[[ -x "$ARMBIAN/compile.sh" ]] || {
    echo "ERROR: Armbian compile.sh not found: $ARMBIAN/compile.sh" >&2
    exit 1
}

mkdir -p "$OUT"

ARMBIAN_COMMIT="$(git -C "$ARMBIAN" rev-parse HEAD)"

echo "Resolving effective Armbian configuration..."
echo "Board:          $BOARD"
echo "Branch:         $BRANCH"
echo "Armbian:        $ARMBIAN"
echo "Armbian commit: $ARMBIAN_COMMIT"

#
# Let Armbian evaluate the real board/family/branch configuration.
#
if ! (
    cd "$ARMBIAN"

    ALLOW_ROOT=yes \
    CONFIG_DEFS_ONLY=yes \
    ANSI_COLOR=none \
    USE_TMPFS=no \
    ./compile.sh \
        "BOARD=$BOARD" \
        "BRANCH=$BRANCH" \
        config-dump-json
) >"$RAW" 2>"$LOG"
then
    echo "ERROR: Armbian config-dump-json failed" >&2
    cat "$LOG" >&2 || true
    exit 1
fi

python3 - \
    "$RAW" \
    "$JSON" \
    "$ENVFILE" \
    "$BOARD" \
    "$BRANCH" \
    "$ARMBIAN_COMMIT" <<'PY'
import json
import shlex
import sys
from pathlib import Path

raw_path = Path(sys.argv[1])
json_path = Path(sys.argv[2])
env_path = Path(sys.argv[3])
requested_board = sys.argv[4]
requested_branch = sys.argv[5]
armbian_commit = sys.argv[6]

text = raw_path.read_text(
    encoding="utf-8",
    errors="replace",
)

#
# Do NOT assume that the JSON occupies exactly one physical line or
# that there is no informational output before/after it.
#
decoder = json.JSONDecoder()
objects = []

for pos, char in enumerate(text):
    if char != "{":
        continue

    try:
        obj, end = decoder.raw_decode(text[pos:])
    except json.JSONDecodeError:
        continue

    if isinstance(obj, dict):
        objects.append(obj)

if not objects:
    print(
        "ERROR: no JSON object found in Armbian config dump",
        file=sys.stderr,
    )
    print(
        f"Raw output preserved in: {raw_path}",
        file=sys.stderr,
    )
    raise SystemExit(1)

#
# If stdout happened to contain more than one JSON object, select the
# one that looks like an Armbian board configuration.
#
important = {
    "BOARD",
    "BOARD_NAME",
    "BOARDFAMILY",
    "LINUXFAMILY",
    "BRANCH",
    "KERNEL_TARGET",
    "BOOT_FDT_FILE",
    "BOOTCONFIG",
    "BOOTSOURCE",
    "BOOTBRANCH",
}

def score(obj):
    return sum(key in obj for key in important)

payload = max(objects, key=score)

if score(payload) < 3:
    print(
        "ERROR: JSON found, but it does not look like an "
        "Armbian board configuration",
        file=sys.stderr,
    )
    print(
        f"Raw output preserved in: {raw_path}",
        file=sys.stderr,
    )
    raise SystemExit(1)

def scalar(value):
    if value is None:
        return ""

    if isinstance(value, bool):
        return "yes" if value else "no"

    if isinstance(value, (list, dict)):
        return json.dumps(
            value,
            separators=(",", ":"),
            sort_keys=True,
        )

    return str(value)

keys = [
    "BOARD",
    "BOARD_NAME",
    "BOARD_VENDOR",
    "BOARDFAMILY",
    "LINUXFAMILY",
    "BRANCH",
    "KERNEL_TARGET",
    "ARCH",
    "KERNELSOURCE",
    "KERNELBRANCH",
    "KERNELPATCHDIR",
    "LINUXCONFIG",
    "KERNEL_MAJOR_MINOR",

    "BOOT_FDT_FILE",
    "GRUB_FDT_FILE",
    "OVERLAY_DIR",
    "ARMBIAN_WILL_BUILD_UBOOT",
    "BOOTCONFIG",
    "BOOTSOURCE",
    "BOOTBRANCH",
    "BOOTPATCHDIR",
    "BOOTDIR",
    "BOOT_SOC",
    "BOOT_SCENARIO",

    "IMAGE_PARTITION_TABLE",
    "OFFSET",
    "BOOTSIZE",
    "UEFISIZE",
    "UEFI_FS_LABEL",
    "UEFI_MOUNT_POINT",
]

resolved = {
    key: scalar(payload.get(key, ""))
    for key in keys
}

#
# BOARD and BRANCH are explicit inputs to Armbian. Older/newer
# config-dump variants may omit them from captured variables.
#
if not resolved["BOARD"]:
    resolved["BOARD"] = requested_board

if not resolved["BRANCH"]:
    resolved["BRANCH"] = requested_branch

if not resolved["LINUXFAMILY"]:
    resolved["LINUXFAMILY"] = resolved["BOARDFAMILY"]

resolved["ARMBIAN_COMMIT"] = armbian_commit

if resolved["BOARD"] != requested_board:
    raise SystemExit(
        "ERROR: effective BOARD mismatch: "
        f"{resolved['BOARD']!r} != {requested_board!r}"
    )

if resolved["BRANCH"] != requested_branch:
    raise SystemExit(
        "ERROR: effective BRANCH mismatch: "
        f"{resolved['BRANCH']!r} != {requested_branch!r}"
    )

for required in [
    "BOARD_NAME",
    "BOARDFAMILY",
    "LINUXFAMILY",
    "KERNEL_TARGET",
]:
    if not resolved[required]:
        raise SystemExit(
            f"ERROR: effective Armbian value missing: {required}"
        )

json_path.write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)

with env_path.open("w", encoding="utf-8") as f:
    for key in keys + ["ARMBIAN_COMMIT"]:
        f.write(
            f"{key}={shlex.quote(resolved[key])}\n"
        )

print()
print("===== EFFECTIVE ARMBIAN CONFIG =====")

for key in [
    "BOARD",
    "BOARD_NAME",
    "BOARD_VENDOR",
    "BOARDFAMILY",
    "LINUXFAMILY",
    "BRANCH",
    "KERNEL_TARGET",
    "ARCH",
    "KERNELSOURCE",
    "KERNELBRANCH",
    "KERNELPATCHDIR",
    "LINUXCONFIG",
    "KERNEL_MAJOR_MINOR",
    "BOOT_FDT_FILE",
    "GRUB_FDT_FILE",
    "OVERLAY_DIR",
    "ARMBIAN_WILL_BUILD_UBOOT",
    "BOOTCONFIG",
    "BOOTSOURCE",
    "BOOTBRANCH",
    "BOOTPATCHDIR",
    "BOOTDIR",
    "BOOT_SOC",
    "BOOT_SCENARIO",
    "IMAGE_PARTITION_TABLE",
    "OFFSET",
    "BOOTSIZE",
    "UEFISIZE",
    "UEFI_FS_LABEL",
    "UEFI_MOUNT_POINT",
    "ARMBIAN_COMMIT",
]:
    print(f"{key}={resolved[key]}")

print()
print(f"JSON: {json_path}")
print(f"ENV:  {env_path}")
PY
