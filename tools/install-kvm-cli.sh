#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?Usage: $0 <rootfs>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PAYLOAD="$ROOT/tools/kvm-cli"
XML_SOURCE="$ROOT/profiles/kvm-cli/service_kvm-over-ip.xml"

ROOTFS="$(readlink -f "$ROOTFS")"

[[ -d "$ROOTFS" && "$ROOTFS" != / ]] || {
    echo "ERROR: refusing unsafe root filesystem path: $ROOTFS" >&2
    exit 1
}

[[ $EUID -eq 0 ]] || {
    echo "ERROR: install-kvm-cli.sh must run as root" >&2
    exit 1
}

for mountpoint_path in dev proc sys run; do
    mountpoint -q "$ROOTFS/$mountpoint_path" || {
        echo "ERROR: chroot mount missing: $ROOTFS/$mountpoint_path" >&2
        exit 1
    }
done

for path in \
    "$XML_SOURCE" \
    "$PAYLOAD/service_kvm_over_ip.py" \
    "$PAYLOAD/vyos-kvm-video-runner" \
    "$PAYLOAD/vyos-kvm-video.service" \
    "$PAYLOAD/vyos-kvm-mediamtx.service" \
    "$PAYLOAD/merge-vyos-reference.py"
do
    [[ -s "$path" ]] || {
        echo "ERROR: KVM CLI payload missing: $path" >&2
        exit 1
    }
done

TEMPLATE_ROOT="$ROOTFS/opt/vyatta/share/vyatta-cfg/templates/service/kvm-over-ip"
CONF_MODE="$ROOTFS/usr/libexec/vyos/conf_mode/service_kvm_over_ip.py"
LIBEXEC="$ROOTFS/usr/local/libexec"
UNIT_DIR="$ROOTFS/etc/systemd/system"
DATA_DIR="$ROOTFS/usr/share/vyos-arm64-board-builder/kvm-cli"
XML_DIR="$DATA_DIR/interface-definitions"

install -d -m 0755 \
    "$TEMPLATE_ROOT" \
    "$(dirname "$CONF_MODE")" \
    "$LIBEXEC" \
    "$UNIT_DIR" \
    "$XML_DIR"

install -m 0755 "$PAYLOAD/service_kvm_over_ip.py" "$CONF_MODE"
install -m 0755 "$PAYLOAD/vyos-kvm-video-runner" "$LIBEXEC/vyos-kvm-video-runner"
install -m 0644 "$PAYLOAD/vyos-kvm-video.service" "$UNIT_DIR/vyos-kvm-video.service"
install -m 0644 "$PAYLOAD/vyos-kvm-mediamtx.service" "$UNIT_DIR/vyos-kvm-mediamtx.service"
install -m 0755 "$PAYLOAD/merge-vyos-reference.py" "$LIBEXEC/vyos-kvm-merge-reference"
install -m 0644 "$XML_SOURCE" "$XML_DIR/service_kvm-over-ip.xml"

rm -rf "$TEMPLATE_ROOT"
install -d -m 0755 "$TEMPLATE_ROOT"

write_node()
{
    local rel="$1"
    local dir="$TEMPLATE_ROOT"

    [[ -n "$rel" ]] && dir="$TEMPLATE_ROOT/$rel"
    install -d -m 0755 "$dir"
    cat > "$dir/node.def"
}

write_node "" <<'EOF'
priority: 1000
help: KVM-over-IP service
end: sudo sh -c "${vyshim} /usr/libexec/vyos/conf_mode/service_kvm_over_ip.py"
EOF

write_node "video" <<'EOF'
help: Video capture and streaming
EOF

write_node "video/backend" <<'EOF'
type: txt
help: Video streaming backend
val_help: ustreamer; MJPEG over HTTP using uStreamer
val_help: gstreamer; H.264 using GStreamer and MediaMTX/WebRTC
val_help: ffmpeg; H.264 using FFmpeg and MediaMTX/WebRTC
allowed: echo "ustreamer gstreamer ffmpeg"
EOF

write_node "video/device" <<'EOF'
type: txt
help: Override V4L2 capture device
val_help: /dev/videoN; V4L2 capture device
EOF

write_node "video/resolution" <<'EOF'
type: txt
help: Requested capture resolution
val_help: WIDTHxHEIGHT; Capture resolution, for example 1920x1080
EOF

write_node "video/framerate" <<'EOF'
type: txt
help: Requested capture frame rate
val_help: u32:1-240; Frames per second
EOF

write_node "video/bitrate" <<'EOF'
type: txt
help: H.264 target bitrate in kbit/s (FFmpeg/GStreamer only; internal default 8000)
val_help: u32:250-100000; H.264 bitrate in kbit/s
EOF

write_node "video/gop" <<'EOF'
type: txt
help: H.264 GOP length in frames (FFmpeg/GStreamer only; internal default 60)
val_help: u32:1-600; Distance between key frames
EOF

write_node "video/listen-address" <<'EOF'
type: txt
help: Browser-facing stream listen address (internal default 0.0.0.0)
val_help: ipv4; IPv4 listen address
EOF

write_node "video/port" <<'EOF'
type: txt
help: Browser-facing stream port (internal default 8889)
val_help: u32:1-65535; TCP port
EOF

write_node "keyboard" <<'EOF'
help: Enable USB HID keyboard
EOF

write_node "mouse" <<'EOF'
help: USB HID mouse functions
EOF

write_node "mouse/absolute" <<'EOF'
help: Enable absolute USB HID mouse
EOF

write_node "mouse/relative" <<'EOF'
help: Enable relative USB HID mouse
EOF

write_node "usb" <<'EOF'
help: USB gadget routing
EOF

write_node "usb/port" <<'EOF'
type: txt
help: Provider-defined semantic USB gadget port
val_help: name; Semantic provider port, for example dedicated
EOF

write_node "virtual-media" <<'EOF'
help: USB read-only CD-ROM virtual media
EOF

write_node "virtual-media/file" <<'EOF'
type: txt
help: ISO image below /config/kvm-over-ip/media
val_help: /config/kvm-over-ip/media/FILE.iso; Read-only virtual CD-ROM ISO
EOF

chroot "$ROOTFS" /usr/bin/python3 \
    /usr/local/libexec/vyos-kvm-merge-reference \
    /usr/share/vyos-arm64-board-builder/kvm-cli/interface-definitions

chroot "$ROOTFS" /usr/bin/python3 -m py_compile \
    /usr/libexec/vyos/conf_mode/service_kvm_over_ip.py

chroot "$ROOTFS" /usr/bin/bash -n \
    /usr/local/libexec/vyos-kvm-video-runner

echo "Installed native VyOS KVM-over-IP CLI and runtime"
