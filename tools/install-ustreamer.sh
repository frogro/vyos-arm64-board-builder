#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?Usage: $0 <rootfs> <artifact-dir>}"
ARTIFACTS="${2:?Usage: $0 <rootfs> <artifact-dir>}"

for file in \
    ustreamer \
    ustreamer-dump \
    LICENSE \
    LICENSE.libjpeg-turbo \
    build.env \
    SHA256SUMS
do
    [[ -s "$ARTIFACTS/$file" ]] || {
        echo "ERROR: µStreamer artifact missing: $ARTIFACTS/$file" >&2
        exit 1
    }
done

(
    cd "$ARTIFACTS"
    sha256sum -c SHA256SUMS
)

install -D -m 0755 "$ARTIFACTS/ustreamer" "$ROOTFS/usr/local/bin/ustreamer"
install -D -m 0755 "$ARTIFACTS/ustreamer-dump" "$ROOTFS/usr/local/bin/ustreamer-dump"
install -D -m 0644 "$ARTIFACTS/LICENSE" "$ROOTFS/usr/share/doc/ustreamer/LICENSE"
install -D -m 0644 "$ARTIFACTS/LICENSE.libjpeg-turbo" \
    "$ROOTFS/usr/share/doc/ustreamer/LICENSE.libjpeg-turbo"
install -D -m 0644 "$ARTIFACTS/build.env" \
    "$ROOTFS/usr/share/vyos-arm64-board-builder/ustreamer-build.env"

if [[ "$(uname -m)" == "aarch64" ]]; then
    for binary in ustreamer ustreamer-dump; do
        missing="$(
            chroot "$ROOTFS" ldd "/usr/local/bin/$binary" |
                grep 'not found' || true
        )"
        [[ -z "$missing" ]] || {
            echo "ERROR: $binary runtime dependency missing:" >&2
            echo "$missing" >&2
            exit 1
        }
    done
fi

echo "Installed profile-scoped µStreamer into VyOS root filesystem"
