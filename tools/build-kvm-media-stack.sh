#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOARD="${1:?Usage: $0 <board>}"

COMPONENTS_FILE="${KVM_MEDIA_COMPONENTS_FILE:-$ROOT/profiles/kvm-hardware/rk3588-synopsys-hdmirx-media-components.txt}"
WORK="$ROOT/work/build/$BOARD/kvm-media"
CHROOT="$WORK/bookworm-root"
ARTIFACTS="$ROOT/work/build/$BOARD/artifacts/kvm-media"

MPP_REPO="${MPP_REPO:-https://github.com/rockchip-linux/mpp.git}"
MPP_COMMIT="${MPP_COMMIT:-c08762ebfadeb4e986d2fed993bc7a54862d3ebe}"

FFMPEG_REPO="${FFMPEG_REPO:-https://github.com/nyanmisaka/ffmpeg-rockchip.git}"
FFMPEG_COMMIT="${FFMPEG_COMMIT:-d90e3a1c18d7929383cf88c1b3da2e2d1c966cbf}"

GST_ROCKCHIP_REPO="${GST_ROCKCHIP_REPO:-https://github.com/Meonardo/gst-rockchip.git}"
GST_ROCKCHIP_COMMIT="${GST_ROCKCHIP_COMMIT:-99c594d3090ee1b4721ef0a9c1e4a99ea3de52e9}"

MEDIAMTX_VERSION="${MEDIAMTX_VERSION:-v1.20.0}"
MEDIAMTX_ARCHIVE="mediamtx_${MEDIAMTX_VERSION}_linux_arm64.tar.gz"
MEDIAMTX_BASE_URL="https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}"

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

warn()
{
    echo "WARNING: $*" >&2
}

[[ $EUID -eq 0 ]] || die "build-kvm-media-stack.sh must run as root"
[[ "$(uname -m)" == "aarch64" ]] || die "native ARM64 build host required"
[[ -s "$COMPONENTS_FILE" ]] || die "component list missing: $COMPONENTS_FILE"

for command in debootstrap git chroot install sha256sum readelf curl tar awk sed grep find; do
    command -v "$command" >/dev/null 2>&1 || die "required command missing: $command"
done

declare -A COMPONENT_MODE=()
while IFS='|' read -r component mode extra; do
    [[ -n "$component" ]] || continue
    [[ -z "${extra:-}" ]] || die "invalid component line: $component|$mode|$extra"
    case "$mode" in
        required|optional) ;;
        *) die "invalid mode '$mode' for component '$component'" ;;
    esac
    COMPONENT_MODE["$component"]="$mode"
done < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$COMPONENTS_FILE")

enabled()
{
    [[ -n "${COMPONENT_MODE[$1]:-}" ]]
}

mode_of()
{
    printf '%s\n' "${COMPONENT_MODE[$1]:-disabled}"
}

for component in "${!COMPONENT_MODE[@]}"; do
    case "$component" in
        libmpp|ffmpeg-rockchip|mediamtx|gstreamer-rockchip) ;;
        *) die "unknown media component: $component" ;;
    esac
done

if enabled ffmpeg-rockchip && ! enabled libmpp; then
    die "ffmpeg-rockchip requires libmpp"
fi
if enabled gstreamer-rockchip && ! enabled libmpp; then
    die "gstreamer-rockchip requires libmpp"
fi

rm -rf "$WORK" "$ARTIFACTS"
mkdir -p "$WORK" "$ARTIFACTS/bin" "$ARTIFACTS/lib" "$ARTIFACTS/gstreamer" "$ARTIFACTS/etc" "$ARTIFACTS/source"

cleanup_work()
{
    rm -rf "$WORK"
}
trap cleanup_work EXIT

debootstrap --arch=arm64 --variant=minbase bookworm "$CHROOT" https://deb.debian.org/debian
install -D -m 0644 /etc/resolv.conf "$CHROOT/etc/resolv.conf"

chroot "$CHROOT" apt-get update
chroot "$CHROOT" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates git build-essential cmake pkg-config libdrm-dev curl xz-utils tar file

clone_pinned()
{
    local repo="$1"
    local commit="$2"
    local dst="$3"

    git clone --quiet --no-checkout "$repo" "$dst"
    git -C "$dst" fetch --quiet --depth=1 origin "$commit"
    git -C "$dst" checkout --quiet --detach "$commit"
    [[ "$(git -C "$dst" rev-parse HEAD)" == "$commit" ]] || die "source commit mismatch for $repo"
}

if enabled libmpp; then
    echo "===== BUILDING LIBMPP ====="
    clone_pinned "$MPP_REPO" "$MPP_COMMIT" "$CHROOT/build/mpp"

    chroot "$CHROOT" /bin/bash -lc 'set -euo pipefail; cmake -S /build/mpp -B /build/mpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_TEST=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_INSTALL_PREFIX=/usr/local; cmake --build /build/mpp/build -j"${JOBS:-4}"; cmake --install /build/mpp/build; ldconfig'

    MPP_INFO="$(find "$CHROOT/build/mpp/build" -type f -name mpp_info_test -perm -111 -print -quit)"
    MPI_ENC="$(find "$CHROOT/build/mpp/build" -type f -name mpi_enc_test -perm -111 -print -quit)"
    [[ -n "$MPP_INFO" ]] || die "mpp_info_test was not built"
    [[ -n "$MPI_ENC" ]] || die "mpi_enc_test was not built"

    install -m 0755 "$MPP_INFO" "$ARTIFACTS/bin/mpp_info_test"
    install -m 0755 "$MPI_ENC" "$ARTIFACTS/bin/mpi_enc_test"

    while IFS= read -r lib; do
        [[ -e "$lib" || -L "$lib" ]] && cp -a "$lib" "$ARTIFACTS/lib/"
    done < <(find "$CHROOT/usr/local" \( -type f -o -type l \) -name 'librockchip_mpp.so*' -print)

    compgen -G "$ARTIFACTS/lib/librockchip_mpp.so*" >/dev/null || die "librockchip_mpp shared library missing after install"

    git -C "$CHROOT/build/mpp" archive --format=tar.gz --prefix="mpp-${MPP_COMMIT}/" --output="$ARTIFACTS/source/mpp-${MPP_COMMIT}.tar.gz" HEAD
fi

if enabled ffmpeg-rockchip; then
    echo "===== BUILDING FFMPEG-ROCKCHIP ====="
    clone_pinned "$FFMPEG_REPO" "$FFMPEG_COMMIT" "$CHROOT/build/ffmpeg-rockchip"

    chroot "$CHROOT" /bin/bash -lc 'set -euo pipefail; export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/local/lib/aarch64-linux-gnu/pkgconfig; cd /build/ffmpeg-rockchip; ./configure --prefix=/usr/local --disable-debug --disable-doc --disable-shared --enable-static --disable-autodetect --enable-version3 --enable-libdrm --enable-rkmpp; make -j"${JOBS:-4}"; make install; ldconfig; /usr/local/bin/ffmpeg -hide_banner -encoders | grep -q "h264_rkmpp"; /usr/local/bin/ffmpeg -hide_banner -h encoder=h264_rkmpp | grep -q "bgr24"'

    install -m 0755 "$CHROOT/usr/local/bin/ffmpeg" "$ARTIFACTS/bin/ffmpeg-rockchip"
    install -m 0755 "$CHROOT/usr/local/bin/ffprobe" "$ARTIFACTS/bin/ffprobe-rockchip"
    chroot "$CHROOT" ldd /usr/local/bin/ffmpeg > "$ARTIFACTS/ffmpeg-rockchip.ldd.txt" || true
    chroot "$CHROOT" /usr/local/bin/ffmpeg -hide_banner -encoders > "$ARTIFACTS/ffmpeg-encoders.txt"
    chroot "$CHROOT" /usr/local/bin/ffmpeg -hide_banner -h encoder=h264_rkmpp > "$ARTIFACTS/h264-rkmpp-help.txt"

    git -C "$CHROOT/build/ffmpeg-rockchip" archive --format=tar.gz --prefix="ffmpeg-rockchip-${FFMPEG_COMMIT}/" --output="$ARTIFACTS/source/ffmpeg-rockchip-${FFMPEG_COMMIT}.tar.gz" HEAD
fi

GST_STATUS=disabled
if enabled gstreamer-rockchip; then
    GST_MODE="$(mode_of gstreamer-rockchip)"
    GST_INSPECT_LOG="$ARTIFACTS/gstreamer/mpph264enc-inspect.txt"
    GST_LDD_LOG="$ARTIFACTS/gstreamer/libgstrockchipmpp.ldd.txt"
    echo "===== BUILDING GSTREAMER-ROCKCHIP ====="

    if (
        set -euo pipefail
        chroot "$CHROOT" env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends meson ninja-build python3 gstreamer1.0-tools libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
        clone_pinned "$GST_ROCKCHIP_REPO" "$GST_ROCKCHIP_COMMIT" "$CHROOT/build/gst-rockchip"
        chroot "$CHROOT" /bin/bash -lc 'set -euo pipefail; export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/local/lib/aarch64-linux-gnu/pkgconfig; meson setup /build/gst-rockchip/build /build/gst-rockchip --prefix=/usr/local --libdir=lib/aarch64-linux-gnu --buildtype=release -Drockchipmpp=enabled -Drga=disabled -Drkximage=disabled -Dkmssrc=disabled -Dvpxalphadec=disabled; ninja -C /build/gst-rockchip/build -j"${JOBS:-4}"; meson install -C /build/gst-rockchip/build; ldconfig; rm -f /tmp/vyos-kvm-gst-registry.bin; GST_REGISTRY=/tmp/vyos-kvm-gst-registry.bin GST_PLUGIN_PATH=/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0 gst-inspect-1.0 mpph264enc >/tmp/mpph264enc.txt 2>&1'
        GST_PLUGIN="$(find "$CHROOT/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0" -type f -name 'libgstrockchipmpp.so*' -print -quit)"
        [[ -n "$GST_PLUGIN" ]]
        GST_PLUGIN_REL="${GST_PLUGIN#$CHROOT}"
        chroot "$CHROOT" /usr/bin/ldd "$GST_PLUGIN_REL" > "$GST_LDD_LOG"
        ! grep -q 'not found' "$GST_LDD_LOG"
        install -m 0755 "$GST_PLUGIN" "$ARTIFACTS/gstreamer/libgstrockchipmpp.so"
        cp "$CHROOT/tmp/mpph264enc.txt" "$GST_INSPECT_LOG"
        git -C "$CHROOT/build/gst-rockchip" archive --format=tar.gz --prefix="gst-rockchip-${GST_ROCKCHIP_COMMIT}/" --output="$ARTIFACTS/source/gst-rockchip-${GST_ROCKCHIP_COMMIT}.tar.gz" HEAD
    ); then
        GST_STATUS=pass
    else
        GST_STATUS=failed
        if [[ -s "$CHROOT/tmp/mpph264enc.txt" && ! -s "$GST_INSPECT_LOG" ]]; then
            cp "$CHROOT/tmp/mpph264enc.txt" "$GST_INSPECT_LOG"
        fi
        rm -f "$ARTIFACTS/gstreamer/libgstrockchipmpp.so" "$ARTIFACTS/source/gst-rockchip-${GST_ROCKCHIP_COMMIT}.tar.gz"

        if [[ -s "$GST_INSPECT_LOG" ]]; then
            echo "===== GSTREAMER-ROCKCHIP GST-INSPECT FAILURE LOG =====" >&2
            cat "$GST_INSPECT_LOG" >&2
        fi
        if [[ -s "$GST_LDD_LOG" ]]; then
            echo "===== GSTREAMER-ROCKCHIP LDD LOG =====" >&2
            cat "$GST_LDD_LOG" >&2
        fi

        if [[ "$GST_MODE" == required ]]; then
            die "required gstreamer-rockchip build or validation failed"
        fi

        warn "optional gstreamer-rockchip build or validation failed; continuing without it"
    fi
fi

if enabled mediamtx; then
    echo "===== FETCHING MEDIAMTX ====="
    MTX_DIR="$WORK/mediamtx-download"
    mkdir -p "$MTX_DIR"

    curl -fL --retry 3 "$MEDIAMTX_BASE_URL/$MEDIAMTX_ARCHIVE" -o "$MTX_DIR/$MEDIAMTX_ARCHIVE"
    curl -fL --retry 3 "$MEDIAMTX_BASE_URL/checksums.sha256" -o "$MTX_DIR/checksums.sha256"

    EXPECTED="$(awk -v f="$MEDIAMTX_ARCHIVE" '$2 == f || $2 == "*" f {print $1; exit}' "$MTX_DIR/checksums.sha256")"
    [[ -n "$EXPECTED" ]] || die "MediaMTX checksum entry not found for $MEDIAMTX_ARCHIVE"

    ACTUAL="$(sha256sum "$MTX_DIR/$MEDIAMTX_ARCHIVE" | awk '{print $1}')"
    [[ "$ACTUAL" == "$EXPECTED" ]] || die "MediaMTX checksum mismatch: expected=$EXPECTED actual=$ACTUAL"

    mkdir -p "$MTX_DIR/unpacked"
    tar -xzf "$MTX_DIR/$MEDIAMTX_ARCHIVE" -C "$MTX_DIR/unpacked"

    [[ -x "$MTX_DIR/unpacked/mediamtx" ]] || die "MediaMTX binary missing in release archive"
    install -m 0755 "$MTX_DIR/unpacked/mediamtx" "$ARTIFACTS/bin/mediamtx"
    [[ -s "$MTX_DIR/unpacked/mediamtx.yml" ]] && install -m 0644 "$MTX_DIR/unpacked/mediamtx.yml" "$ARTIFACTS/etc/mediamtx.yml"
    [[ -s "$MTX_DIR/unpacked/LICENSE" ]] && install -m 0644 "$MTX_DIR/unpacked/LICENSE" "$ARTIFACTS/LICENSE.mediamtx"

    "$ARTIFACTS/bin/mediamtx" --version > "$ARTIFACTS/mediamtx-version.txt"
fi

cat > "$ARTIFACTS/build.env" <<EOF
MPP_COMMIT=$MPP_COMMIT
FFMPEG_ROCKCHIP_COMMIT=$FFMPEG_COMMIT
MEDIAMTX_VERSION=$MEDIAMTX_VERSION
GSTREAMER_ROCKCHIP_COMMIT=$GST_ROCKCHIP_COMMIT
GSTREAMER_ROCKCHIP_STATUS=$GST_STATUS
LIBMPP_MODE=$(mode_of libmpp)
FFMPEG_ROCKCHIP_MODE=$(mode_of ffmpeg-rockchip)
MEDIAMTX_MODE=$(mode_of mediamtx)
GSTREAMER_ROCKCHIP_MODE=$(mode_of gstreamer-rockchip)
BUILD_DISTRIBUTION=debian-bookworm
EOF

cp "$COMPONENTS_FILE" "$ARTIFACTS/components.txt"

(
    cd "$ARTIFACTS"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

echo
echo "===== KVM MEDIA STACK RESULT ====="
cat "$ARTIFACTS/build.env"
echo
find "$ARTIFACTS" -maxdepth 3 -type f -printf '%P %s bytes\n' | sort
echo
echo "PASS: KVM media stack artifacts prepared"

rm -rf "$CHROOT"
