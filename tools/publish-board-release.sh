#!/usr/bin/env bash
set -euo pipefail
BOARD="${1:?board required}"
BUILD_ROOT="${2:?build directory required}"
source "$BUILD_ROOT/release.env"
source "$BUILD_ROOT/selection/feature-profiles.env"
REPO="$(python3 tools/board-update-channel.py "$BOARD" "$BUILD_PROFILE")"
if [[ "$BOARD" == raspberry-pi-5 && "$BUILD_PROFILE" == network ]]; then
    REPO=VyARM-Community/raspberry-pi-5
    # Native FAT lifecycle is experimental: keep public publication installation-only.
    (cd "$BUILD_ROOT" && sha256sum -c "$RELEASE_BASENAME.img.xz.sha256")
    python3 - "$BUILD_ROOT/board-manifest.json" <<'PYMANIFEST'
import json, sys
m = json.load(open(sys.argv[1]))
assert (m['board'], m['profile'], m['architecture'], m['update_provider']) == ('raspberry-pi-5', 'network', 'arm64', 'firmware-files')
PYMANIFEST
    cat > "$BUILD_ROOT/BOARD_RELEASE_NOTES.md" <<EOFPI
VyOS ${VYOS_VERSION} for Raspberry Pi 5, with additional network, Wi-Fi and cellular modem support.

Initial installation: \`${RELEASE_BASENAME}.img.xz\`. Verify the adjacent SHA-256 checksum before flashing.

Boot path: native Raspberry Pi EEPROM/firmware, FAT boot partition, matching kernel/initramfs and BCM2712 Device Tree. This exact image requires hardware testing. Experimental FAT image-switch hooks are included for validation, but in-place ISO updates are not yet hardware-validated; no update feed is published for this board.

Published Rolling reference: ${ROLLING_REFERENCE:-not specified}. Package versions may differ due to the later build against the rolling repository.
EOFPI
    gh release create "$RELEASE_TAG" --repo "$REPO" --draft \
        --title "VyOS ${VYOS_VERSION} for Raspberry Pi 5" \
        --notes-file "$BUILD_ROOT/BOARD_RELEASE_NOTES.md" \
        "$BUILD_ROOT/$RELEASE_BASENAME.img.xz" "$BUILD_ROOT/$RELEASE_BASENAME.img.xz.sha256" \
        "$BUILD_ROOT/board-manifest.json"
    gh release edit "$RELEASE_TAG" --repo "$REPO" --draft=false --latest
    exit 0
fi
[[ -n "$REPO" ]] || exit 0
ISO="$BUILD_ROOT/$RELEASE_BASENAME.iso"
python3 tools/board-update-channel.py "$BOARD" "$BUILD_PROFILE" \
    --manifest "$BUILD_ROOT/board-manifest.json" --iso "$ISO" \
    --tag "$RELEASE_TAG" --version "$VYOS_VERSION" --output "$BUILD_ROOT/image-version.json"
(cd "$BUILD_ROOT" && sha256sum -c "$RELEASE_BASENAME.img.xz.sha256")
cat > "$BUILD_ROOT/BOARD_RELEASE_NOTES.md" <<EOF
VyOS ${VYOS_VERSION} for ${BOARD}, with additional network, Wi-Fi and cellular modem drivers and firmware for supported hardware.

- Initial installation/recovery: \`${RELEASE_BASENAME}.img.xz\`
- Compatible system-image update: \`${RELEASE_BASENAME}.iso\`
- Verify downloads with the adjacent SHA-256 checksum files.
- Native update feed: https://github.com/${REPO}/releases/latest/download/image-version.json

Published Rolling reference: ${ROLLING_REFERENCE:-not specified}. Package versions may differ because this image is built later against the rolling package repository. Board-specific additions are intentional differences.

These files are identical to the [source build release](https://github.com/${GITHUB_REPOSITORY}/releases/tag/${RELEASE_TAG}). Builder commit: ${GITHUB_SHA}.

Automated build checks passed. This exact image still requires hardware testing. See the repository README for installation and update instructions.
EOF
# Keep the previous channel intact until all assets have been uploaded.
gh release create "$RELEASE_TAG" --repo "$REPO" --draft \
    --title "VyOS ${VYOS_VERSION} for ${BOARD}" \
    --notes-file "$BUILD_ROOT/BOARD_RELEASE_NOTES.md" \
    "$ISO" "$ISO.sha256" \
    "$BUILD_ROOT/$RELEASE_BASENAME.img.xz" "$BUILD_ROOT/$RELEASE_BASENAME.img.xz.sha256" \
    "$BUILD_ROOT/image-version.json" "$BUILD_ROOT/board-manifest.json"
gh release edit "$RELEASE_TAG" --repo "$REPO" --draft=false --latest
