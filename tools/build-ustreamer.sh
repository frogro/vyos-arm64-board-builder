#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOARD="${1:?Usage: $0 <board>}"

USTREAMER_REPO="${USTREAMER_REPO:-https://github.com/pikvm/ustreamer.git}"
USTREAMER_TAG="${USTREAMER_TAG:-v6.56}"
USTREAMER_COMMIT="${USTREAMER_COMMIT:-23dd2f9e66f945eaf8d9273e4cc4f5b7c47da711}"

WORK="$ROOT/work/build/$BOARD/ustreamer"
SOURCE="$WORK/source"
CHROOT="$WORK/bookworm-root"
ARTIFACTS="$ROOT/work/build/$BOARD/artifacts/ustreamer"

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || die "build-ustreamer.sh must run as root"
[[ "$(uname -m)" == "aarch64" ]] || die "native ARM64 build host required"

for command in debootstrap dpkg git install readelf sha256sum; do
    command -v "$command" >/dev/null 2>&1 || die "required command missing: $command"
done

rm -rf "$WORK" "$ARTIFACTS"
mkdir -p "$WORK" "$ARTIFACTS"

git clone --quiet --no-checkout "$USTREAMER_REPO" "$SOURCE"
git -C "$SOURCE" fetch --quiet --depth=1 origin "refs/tags/$USTREAMER_TAG"
git -C "$SOURCE" checkout --quiet "$USTREAMER_COMMIT"

[[ "$(git -C "$SOURCE" rev-parse HEAD)" == "$USTREAMER_COMMIT" ]] ||
    die "µStreamer source commit mismatch"

debootstrap \
    --arch=arm64 \
    --variant=minbase \
    bookworm \
    "$CHROOT" \
    https://deb.debian.org/debian

install -d "$CHROOT/build/ustreamer"
cp -a "$SOURCE/." "$CHROOT/build/ustreamer/"

chroot "$CHROOT" apt-get update
chroot "$CHROOT" env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    --no-install-recommends \
    build-essential \
    libbsd-dev \
    libevent-dev \
    libjpeg62-turbo-dev \
    pkg-config

JPEG_STATIC="/usr/lib/aarch64-linux-gnu/libjpeg.a"
[[ -s "$CHROOT$JPEG_STATIC" ]] ||
    die "static libjpeg archive missing: $JPEG_STATIC"

# VyOS intentionally does not ship libjpeg.so.62. Link only libjpeg-turbo
# statically so the profile remains self-contained without importing a
# foreign shared-library stack into the VyOS root filesystem.
chroot "$CHROOT" sed -i \
    "s|-ljpeg|${JPEG_STATIC}|g" \
    /build/ustreamer/src/Makefile

chroot "$CHROOT" make -C /build/ustreamer -j"${JOBS:-4}" \
    WITH_GPIO=0 \
    WITH_JANUS=0 \
    WITH_PYTHON=0 \
    WITH_SYSTEMD=0 \
    WITH_V4P=0

for binary in ustreamer ustreamer-dump; do
    [[ -x "$CHROOT/build/ustreamer/$binary" ]] ||
        die "built binary missing: $binary"
    install -m 0755 "$CHROOT/build/ustreamer/$binary" "$ARTIFACTS/$binary"
    chroot "$CHROOT" ldd "/build/ustreamer/$binary" > "$ARTIFACTS/$binary.ldd.txt"

    if readelf -d "$ARTIFACTS/$binary" | grep 'NEEDED.*libjpeg' >/dev/null; then
        die "$binary still has a dynamic libjpeg dependency"
    fi
done

install -m 0644 "$SOURCE/LICENSE" "$ARTIFACTS/LICENSE"
install -m 0644 \
    "$CHROOT/usr/share/doc/libjpeg62-turbo/copyright" \
    "$ARTIFACTS/LICENSE.libjpeg-turbo"
git -C "$SOURCE" archive \
    --format=tar.gz \
    --prefix="ustreamer-${USTREAMER_TAG}/" \
    --output="$ARTIFACTS/ustreamer-${USTREAMER_TAG}-source.tar.gz" \
    HEAD

MAX_GLIBC="$(
    readelf --version-info "$ARTIFACTS/ustreamer" |
    grep -oE 'GLIBC_[0-9]+(\.[0-9]+)+' |
    sed 's/^GLIBC_//' |
    sort -Vu |
    tail -1
)"

LIBJPEG_TURBO_VERSION="$(
    chroot "$CHROOT" dpkg-query -W -f='${Version}' libjpeg62-turbo-dev
)"

[[ -n "$MAX_GLIBC" ]] || die "unable to derive required GLIBC version"
dpkg --compare-versions "$MAX_GLIBC" le 2.36 ||
    die "built binary requires GLIBC_$MAX_GLIBC, newer than VyOS GLIBC_2.36"

cat > "$ARTIFACTS/build.env" <<EOF
USTREAMER_TAG=$USTREAMER_TAG
USTREAMER_COMMIT=$USTREAMER_COMMIT
USTREAMER_BUILD_DISTRIBUTION=debian-bookworm
USTREAMER_MAX_GLIBC=$MAX_GLIBC
USTREAMER_LIBJPEG_LINKAGE=static
USTREAMER_LIBJPEG_TURBO_VERSION=$LIBJPEG_TURBO_VERSION
EOF

(
    cd "$ARTIFACTS"
    sha256sum \
        ustreamer \
        ustreamer-dump \
        LICENSE \
        LICENSE.libjpeg-turbo \
        "ustreamer-${USTREAMER_TAG}-source.tar.gz" \
        > SHA256SUMS
)

echo "Built µStreamer $USTREAMER_TAG for ARM64 with maximum GLIBC_$MAX_GLIBC"
echo "Artifacts: $ARTIFACTS"

rm -rf "$CHROOT" "$SOURCE"
