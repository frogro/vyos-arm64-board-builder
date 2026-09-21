#!/bin/bash
set -euo pipefail
export PKG_CONFIG_PATH=/opt/gst/lib/pkgconfig
export LD_LIBRARY_PATH=/opt/gst/lib
common=(--prefix=/opt/gst --libdir=lib --buildtype=release --wrap-mode=nofallback -Dauto_features=disabled)
for package in gstreamer gst-plugins-base gst-plugins-bad; do
  tar -xf "$package-1.28.7.tar.xz"
  case "$package" in
    gstreamer) extra=(-Dtools=enabled) ;;
    gst-plugins-base) extra=(-Dapp=enabled -Dvideotestsrc=enabled -Dvideoconvertscale=enabled -Dtypefind=enabled -Dplayback=enabled) ;;
    gst-plugins-bad) extra=(-Dv4l2codecs=enabled -Dvideoparsers=enabled) ;;
  esac
  meson setup "build-$package" "$package-1.28.7" "${common[@]}" "${extra[@]}"
  ninja -C "build-$package" -j2
  ninja -C "build-$package" install
 done
/opt/gst/bin/gst-inspect-1.0 --version
/opt/gst/bin/gst-inspect-1.0 h264parse
/opt/gst/bin/gst-inspect-1.0 h265parse
# Decoder elements are registered only when matching kernel devices are exposed.
test -s /opt/gst/lib/gstreamer-1.0/libgstv4l2codecs.so
