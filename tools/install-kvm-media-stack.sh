#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?Usage: $0 <rootfs> <artifact-dir>}"
ARTIFACTS="${2:?Usage: $0 <rootfs> <artifact-dir>}"

ROOTFS="$(readlink -f "$ROOTFS")"
ARTIFACTS="$(readlink -f "$ARTIFACTS")"

die()
{
    echo "ERROR: $*" >&2
    exit 1
}

warn()
{
    echo "WARNING: $*" >&2
}

[[ $EUID -eq 0 ]] || die "install-kvm-media-stack.sh must run as root"
[[ -d "$ROOTFS" && "$ROOTFS" != / ]] || die "refusing unsafe root filesystem path: $ROOTFS"
[[ -d "$ARTIFACTS" ]] || die "KVM media artifact directory missing: $ARTIFACTS"
[[ -s "$ARTIFACTS/components.txt" ]] || die "components.txt missing"
[[ -s "$ARTIFACTS/build.env" ]] || die "build.env missing"
[[ -s "$ARTIFACTS/SHA256SUMS" ]] || die "SHA256SUMS missing"

(
    cd "$ARTIFACTS"
    sha256sum -c SHA256SUMS
)

enabled()
{
    local name="$1"
    awk -F'|' -v n="$name" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        $1 == n { found=1 }
        END { exit(found ? 0 : 1) }
    ' "$ARTIFACTS/components.txt"
}

mode_of()
{
    local name="$1"
    awk -F'|' -v n="$name" '
        /^[[:space:]]*#/ || /^[[:space:]]*$/ { next }
        $1 == n { print $2; found=1; exit }
        END { if (!found) exit 1 }
    ' "$ARTIFACTS/components.txt"
}

need_file()
{
    [[ -s "$1" ]] || die "required KVM media artifact missing: $1"
}

if enabled libmpp; then
    need_file "$ARTIFACTS/bin/mpp_info_test"
    need_file "$ARTIFACTS/bin/mpi_enc_test"
    compgen -G "$ARTIFACTS/lib/librockchip_mpp.so*" >/dev/null ||
        die "librockchip_mpp shared library artifacts missing"
fi

if enabled ffmpeg-rockchip; then
    need_file "$ARTIFACTS/bin/ffmpeg-rockchip"
    need_file "$ARTIFACTS/bin/ffprobe-rockchip"
fi

if enabled mediamtx; then
    need_file "$ARTIFACTS/bin/mediamtx"
    need_file "$ARTIFACTS/etc/mediamtx.yml"
fi

PROFILE_DIR="$ROOTFS/usr/share/vyos-arm64-board-builder"
MEDIA_LIB_DIR="$ROOTFS/usr/local/lib/vyos-kvm-media"
GST_PLUGIN_TARGET="/usr/lib/aarch64-linux-gnu/gstreamer-1.0/libgstrockchipmpp.so"
GST_RUNTIME_LOG="$PROFILE_DIR/gstreamer-rockchip-runtime.log"
GST_REGISTRY="/tmp/vyos-kvm-gstreamer-registry.bin"
install -d -m 0755 "$PROFILE_DIR" "$MEDIA_LIB_DIR" "$ROOTFS/usr/local/bin"

if enabled libmpp; then
    install -m 0755 "$ARTIFACTS/bin/mpp_info_test" "$ROOTFS/usr/local/bin/mpp_info_test"
    install -m 0755 "$ARTIFACTS/bin/mpi_enc_test" "$ROOTFS/usr/local/bin/mpi_enc_test"

    while IFS= read -r lib; do
        cp -a "$lib" "$MEDIA_LIB_DIR/"
    done < <(find "$ARTIFACTS/lib" -maxdepth 1 \( -type f -o -type l \) -name 'librockchip_mpp.so*' -print | sort)

    install -D -m 0644 /dev/stdin "$ROOTFS/etc/ld.so.conf.d/vyos-kvm-media.conf" <<'EOF'
/usr/local/lib/vyos-kvm-media
EOF
fi

if enabled ffmpeg-rockchip; then
    install -m 0755 "$ARTIFACTS/bin/ffmpeg-rockchip" "$ROOTFS/usr/local/bin/ffmpeg-rockchip"
    install -m 0755 "$ARTIFACTS/bin/ffprobe-rockchip" "$ROOTFS/usr/local/bin/ffprobe-rockchip"
fi

if enabled mediamtx; then
    install -m 0755 "$ARTIFACTS/bin/mediamtx" "$ROOTFS/usr/local/bin/mediamtx"
    install -D -m 0644 "$ARTIFACTS/etc/mediamtx.yml" "$ROOTFS/etc/mediamtx.yml"
    if [[ -s "$ARTIFACTS/LICENSE.mediamtx" ]]; then
        install -D -m 0644 "$ARTIFACTS/LICENSE.mediamtx" \
            "$ROOTFS/usr/share/doc/mediamtx/LICENSE"
    fi

    install -D -m 0644 /dev/stdin "$ROOTFS/lib/systemd/system/mediamtx.service" <<'EOF'
[Unit]
Description=MediaMTX KVM media server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/mediamtx /etc/mediamtx.yml
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
fi

GST_PLUGIN_INSTALLED=no
if enabled gstreamer-rockchip; then
    GST_MODE="$(mode_of gstreamer-rockchip)"
    if [[ -s "$ARTIFACTS/gstreamer/libgstrockchipmpp.so" ]]; then
        install -D -m 0755 "$ARTIFACTS/gstreamer/libgstrockchipmpp.so" \
            "$ROOTFS$GST_PLUGIN_TARGET"
        GST_PLUGIN_INSTALLED=yes
    elif [[ "$GST_MODE" == required ]]; then
        die "required gstreamer-rockchip plugin artifact missing"
    else
        warn "optional gstreamer-rockchip plugin was not built; continuing without it"
    fi
fi

install -m 0644 "$ARTIFACTS/build.env" "$PROFILE_DIR/kvm-media-build.env"
install -m 0644 "$ARTIFACTS/components.txt" "$PROFILE_DIR/kvm-media-components.txt"

command -v chroot >/dev/null 2>&1 || die "required command missing: chroot"
[[ -x "$ROOTFS/sbin/ldconfig" || -x "$ROOTFS/usr/sbin/ldconfig" ]] ||
    die "target rootfs does not provide ldconfig"
chroot "$ROOTFS" /sbin/ldconfig 2>/dev/null ||
    chroot "$ROOTFS" /usr/sbin/ldconfig

check_ldd()
{
    local binary="$1"
    local missing
    missing="$(
        chroot "$ROOTFS" /usr/bin/ldd "$binary" 2>/dev/null |
            grep 'not found' || true
    )"
    [[ -z "$missing" ]] || {
        echo "$missing" >&2
        die "runtime dependency missing for $binary"
    }
}

if enabled libmpp; then
    check_ldd /usr/local/bin/mpp_info_test
    check_ldd /usr/local/bin/mpi_enc_test
fi

[[ -x "$ROOTFS/usr/bin/ffmpeg" ]] ||
    die "generic ffmpeg package is missing from Profile-D userspace"
[[ -x "$ROOTFS/usr/bin/ffprobe" ]] ||
    die "generic ffprobe package is missing from Profile-D userspace"
chroot "$ROOTFS" /usr/bin/ffmpeg -hide_banner -version >/dev/null ||
    die "generic ffmpeg failed runtime validation"
chroot "$ROOTFS" /usr/bin/ffprobe -hide_banner -version >/dev/null ||
    die "generic ffprobe failed runtime validation"

[[ -x "$ROOTFS/usr/bin/gst-inspect-1.0" ]] ||
    die "generic GStreamer tools are missing from Profile-D userspace"
chroot "$ROOTFS" /usr/bin/gst-inspect-1.0 x264enc >/dev/null 2>&1 ||
    die "generic GStreamer x264enc backend is missing"

if enabled ffmpeg-rockchip; then
    check_ldd /usr/local/bin/ffmpeg-rockchip
    chroot "$ROOTFS" /usr/local/bin/ffmpeg-rockchip -hide_banner -encoders |
        grep -q 'h264_rkmpp' ||
        die "installed ffmpeg-rockchip does not expose h264_rkmpp"
    chroot "$ROOTFS" /usr/local/bin/ffmpeg-rockchip -hide_banner -h encoder=h264_rkmpp |
        grep -q 'bgr24' ||
        die "installed h264_rkmpp does not advertise bgr24 input"
fi

if enabled mediamtx; then
    chroot "$ROOTFS" /usr/local/bin/mediamtx --version >/dev/null ||
        die "installed MediaMTX failed version check"
fi

if [[ "$GST_PLUGIN_INSTALLED" == yes ]]; then
    GST_MODE="$(mode_of gstreamer-rockchip)"
    check_ldd "$GST_PLUGIN_TARGET"
    rm -f "$ROOTFS$GST_REGISTRY" "$GST_RUNTIME_LOG"

    if chroot "$ROOTFS" /usr/bin/env \
        GST_REGISTRY="$GST_REGISTRY" \
        GST_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/gstreamer-1.0 \
        /usr/bin/gst-inspect-1.0 mpph264enc > "$GST_RUNTIME_LOG" 2>&1; then
        echo "gstreamer-rockchip mpph264enc runtime validation: PASS"
    else
        echo "===== GSTREAMER-ROCKCHIP RUNTIME VALIDATION LOG =====" >&2
        cat "$GST_RUNTIME_LOG" >&2 || true

        if [[ "$GST_MODE" == required ]]; then
            die "required gstreamer-rockchip plugin failed runtime validation"
        fi

        warn "optional gstreamer-rockchip plugin failed runtime validation; removing it from image"
        rm -f "$ROOTFS$GST_PLUGIN_TARGET"
        GST_PLUGIN_INSTALLED=no
    fi

    rm -f "$ROOTFS$GST_REGISTRY"
fi

cat > "$PROFILE_DIR/kvm-media-install.env" <<EOF
KVM_MEDIA_FFMPEG_GENERIC=yes
KVM_MEDIA_GSTREAMER_GENERIC=yes
KVM_MEDIA_LIBMPP=$(enabled libmpp && echo yes || echo no)
KVM_MEDIA_FFMPEG_ROCKCHIP=$(enabled ffmpeg-rockchip && echo yes || echo no)
KVM_MEDIA_MEDIAMTX=$(enabled mediamtx && echo yes || echo no)
KVM_MEDIA_GSTREAMER_ROCKCHIP=$GST_PLUGIN_INSTALLED
EOF

echo "Installed Profile-D KVM media stack into VyOS root filesystem"
cat "$PROFILE_DIR/kvm-media-install.env"
