#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARMBIAN="${ARMBIAN:-$ROOT/cache/armbian-build}"

BOARD="${1:?Usage: $0 <board> [branch]}"
BRANCH="${2:-current}"

OUT="$ROOT/work/build/$BOARD/boot"
PACKAGE_OUT="$OUT/package"
ARTIFACT_OUT="$OUT/artifacts"
METADATA_OUT="$OUT/metadata"
EXTRACT_OUT="$OUT/extracted"

mkdir -p \
    "$PACKAGE_OUT" \
    "$ARTIFACT_OUT" \
    "$METADATA_OUT"

#
# Resolve/refresh the normalized manifest first.
#
"$ROOT/tools/resolve-bootchain.sh" "$BOARD" "$BRANCH"

[[ -x "$ARMBIAN/compile.sh" ]] || {
    echo "ERROR: Armbian compile.sh not found: $ARMBIAN/compile.sh" >&2
    exit 1
}

echo
echo "===== BUILDING ARMBIAN U-BOOT ARTIFACT ====="

(
    cd "$ARMBIAN"

    ./compile.sh \
        BOARD="$BOARD" \
        BRANCH="$BRANCH" \
        uboot
)

echo
echo "===== LOCATING U-BOOT PACKAGE ====="

DEB="$(
    find "$ARMBIAN/output/debs" \
        -maxdepth 1 \
        -type f \
        -name "linux-u-boot-${BOARD}-${BRANCH}_*.deb" \
        -printf '%T@ %p\n' \
        2>/dev/null |
        sort -nr |
        head -1 |
        cut -d' ' -f2-
)"

[[ -n "$DEB" && -f "$DEB" ]] || {
    echo "ERROR: U-Boot package not found for ${BOARD}/${BRANCH}" >&2
    exit 1
}

echo "Package: $DEB"

rm -rf "$EXTRACT_OUT"
mkdir -p "$EXTRACT_OUT"

dpkg-deb -x "$DEB" "$EXTRACT_OUT"

#
# Find the board-specific payload directory from the package itself.
#
UBOOT_BIN_DIR="$(
    find "$EXTRACT_OUT/usr/lib" \
        -maxdepth 1 \
        -type d \
        -name "linux-u-boot-${BRANCH}-${BOARD}" \
        -print \
        -quit
)"

if [[ -z "$UBOOT_BIN_DIR" ]]; then
    #
    # Fallback: read the metadata location instead of assuming naming.
    #
    META="$(
        find "$EXTRACT_OUT/usr/lib" \
            -type f \
            -name 'u-boot-metadata.sh' \
            -print \
            -quit
    )"

    [[ -n "$META" ]] || {
        echo "ERROR: u-boot-metadata.sh not found in package" >&2
        exit 1
    }

    UBOOT_BIN_DIR="$(dirname "$META")"
fi

META_MAIN="$UBOOT_BIN_DIR/u-boot-metadata.sh"

[[ -f "$META_MAIN" ]] || {
    echo "ERROR: main U-Boot metadata not found: $META_MAIN" >&2
    exit 1
}

#
# shellcheck disable=SC1090
source "$META_MAIN"

#
# Armbian metadata stores UBOOT_BIN_DIR as the final installed
# absolute path (e.g. /usr/lib/linux-u-boot-current-rock-5b).
# Translate it into the root of the extracted .deb.
#
if [[ -n "${UBOOT_BIN_DIR:-}" ]]; then
    UBOOT_BIN_DIR="${EXTRACT_OUT}${UBOOT_BIN_DIR}"
fi

[[ -d "${UBOOT_BIN_DIR:-}" ]] || {
    echo "ERROR: extracted U-Boot payload directory not found: ${UBOOT_BIN_DIR:-unset}" >&2
    exit 1
}

[[ "${UBOOT_NUM_TARGETS:-0}" -ge 1 ]] || {
    echo "ERROR: package contains no U-Boot targets" >&2
    exit 1
}

rm -rf "$ARTIFACT_OUT" "$METADATA_OUT"
mkdir -p "$ARTIFACT_OUT" "$METADATA_OUT"

#
# Copy package for traceability/reproducibility.
#
cp "$DEB" "$PACKAGE_OUT/"

#
# Preserve installation logic.
#
if [[ -f "$EXTRACT_OUT/usr/lib/u-boot/platform_install.sh" ]]; then
    cp \
        "$EXTRACT_OUT/usr/lib/u-boot/platform_install.sh" \
        "$METADATA_OUT/platform_install.sh"
fi

#
# Preserve main metadata.
#
cp "$META_MAIN" "$METADATA_OUT/"

#
# Process every U-Boot target exported by Armbian.
#
for ((target=1; target<=UBOOT_NUM_TARGETS; target++)); do
    TARGET_META="$UBOOT_BIN_DIR/u-boot-metadata-target-${target}.sh"

    [[ -f "$TARGET_META" ]] || {
        echo "ERROR: target metadata missing: $TARGET_META" >&2
        exit 1
    }

    cp "$TARGET_META" "$METADATA_OUT/"

    #
    # shellcheck disable=SC1090
    source "$TARGET_META"

    for bin in "${UBOOT_TARGET_BINS[@]}"; do
        src="$UBOOT_BIN_DIR/$bin"

        [[ -f "$src" ]] || {
            echo "ERROR: expected U-Boot artifact missing: $src" >&2
            exit 1
        }

        cp "$src" "$ARTIFACT_OUT/"
    done

    for meta_file in \
        "${UBOOT_TARGET_CONFIG:-}" \
        "${UBOOT_TARGET_DEFCONFIG:-}"
    do
        [[ -n "$meta_file" ]] || continue

        if [[ -f "$UBOOT_BIN_DIR/$meta_file" ]]; then
            cp "$UBOOT_BIN_DIR/$meta_file" "$METADATA_OUT/"
        fi
    done
done

#
# Preserve generic U-Boot package resources where useful.
#
if [[ -d "$EXTRACT_OUT/usr/lib/u-boot" ]]; then
    if [[ -f "$EXTRACT_OUT/usr/lib/u-boot/LICENSE" ]]; then
        cp "$EXTRACT_OUT/usr/lib/u-boot/LICENSE" "$METADATA_OUT/"
    fi

    find "$EXTRACT_OUT/usr/lib/u-boot" \
        -maxdepth 1 \
        -type f \
        -name '*defconfig' \
        -exec cp {} "$METADATA_OUT/" \;
fi

echo
echo "===== BOOTCHAIN SUMMARY ====="
echo "Board:              $BOARD"
echo "Branch:             $BRANCH"
echo "Package:            $(basename "$DEB")"
echo "Artifact version:   ${UBOOT_ARTIFACT_VERSION:-unknown}"
echo "U-Boot version:     ${UBOOT_VERSION:-unknown}"
echo "Git source:         ${UBOOT_GIT_SOURCE:-unknown}"
echo "Git revision:       ${UBOOT_GIT_REVISION:-unknown}"
echo "Git branch:         ${UBOOT_GIT_BRANCH:-unknown}"
echo "Patch dirs:         ${UBOOT_GIT_PATCHDIR:-unknown}"
echo "Partition type:     ${UBOOT_PARTITION_TYPE:-unknown}"
echo "Kernel DTB:         ${UBOOT_KERNEL_DTB:-unknown}"
echo "Serial console:     ${UBOOT_KERNEL_SERIALCON:-unknown}"
echo
echo "Artifacts:"
find "$ARTIFACT_OUT" \
    -maxdepth 1 \
    -type f \
    -printf '  %f %s bytes\n' |
    sort

echo
echo "Metadata:"
find "$METADATA_OUT" \
    -maxdepth 1 \
    -type f \
    -printf '  %f\n' |
    sort

echo
echo "Bootchain successfully prepared."
