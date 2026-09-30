#!/bin/bash
# Build only the pinned stateless-codec plugin; keep distro core and libraries.
set -euo pipefail
version=1.26.2
sha256=cb116bfc3722c2de53838899006cafdb3c7c0bc69cd769b33c992a8421a9d844
test "$(pkg-config --modversion gstreamer-1.0)" = "$version"
mkdir -p /src/gstreamer-crop
cd /src/gstreamer-crop
curl --fail --location --retry 3 -o source.tar.xz \
  "https://gstreamer.freedesktop.org/src/gst-plugins-bad/gst-plugins-bad-${version}.tar.xz"
printf '%s  source.tar.xz\n' "$sha256" | sha256sum --check --strict
tar -xf source.tar.xz
cd "gst-plugins-bad-${version}"
git apply --check /tmp/gstreamer-crop/0001-hevc-linear-nv12-crop-copy.patch
git apply /tmp/gstreamer-crop/0001-hevc-linear-nv12-crop-copy.patch
meson setup build --buildtype=release --auto-features=disabled \
  -Dv4l2codecs=enabled -Dtests=disabled -Dexamples=disabled \
  -Dtools=disabled -Dintrospection=disabled
ninja -C build -j2
# meson install strips build-tree RPATHs; stage only this plugin, not its
# internally built codec libraries or other plugins.
DESTDIR=/tmp/gst-crop-install meson install -C build --no-rebuild
plugin=$(find /tmp/gst-crop-install -name libgstv4l2codecs.so -type f)
test -n "$plugin"
test "$(printf '%s\n' "$plugin" | wc -l)" = 1
install -Dm755 "$plugin" "/gst-crop-out$(pkg-config --variable=pluginsdir gstreamer-1.0)/libgstv4l2codecs.so"
install -d /gst-crop-out/opt/profile-g/gstreamer-crop
cp /tmp/gstreamer-crop/* /gst-crop-out/opt/profile-g/gstreamer-crop/
printf 'GStreamer %s\nsource-sha256=%s\n' "$version" "$sha256" \
  > /gst-crop-out/opt/profile-g/gstreamer-crop/source.txt
