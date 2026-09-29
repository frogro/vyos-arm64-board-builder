#!/bin/bash
# Run only inside an isolated native amd64 Debian trixie container with /src.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
test "$(dpkg --print-architecture)" = amd64
dpkg --add-architecture arm64
apt-get update
apt-get install -y --no-install-recommends ca-certificates devscripts equivs crossbuild-essential-arm64
mkdir -p /tmp/vyarm-deps/debian
cp /src/debian/control /tmp/vyarm-deps/debian/control
sed -i 's/^ golang,/ golang:native,/; s/^ generate-ninja,/ generate-ninja:native,/; s/^ ninja-build,/ ninja-build:native,/; s/^ gperf,/ gperf:native,/' /tmp/vyarm-deps/debian/control
apt-get build-dep -y --no-install-recommends -a arm64 -P cross /tmp/vyarm-deps
# Keep ARM64 libc++22. Native Rust helpers use the native default C++ library.
dpkg-query -W > /tmp/vyarm-cross-packages.txt
