#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee /src/vyarm-p010-unit.log) 2>&1
trap 'rc=$?; echo "$rc" > /src/vyarm-p010-unit.exit; date -u; exit "$rc"' EXIT
export DEB_BUILD_PROFILES=cross
export DEB_BUILD_OPTIONS='parallel=8 terse'
export HOST_EXEC_WRAPPER=aarch64-linux-gnu-cross-exe-wrapper
eval "$(dpkg-architecture -aarm64 -s)"
export CXXFLAGS_FOR_BUILD='-O2'
export LDFLAGS_FOR_BUILD=''
date -u
ninja -j8 -C out/Release media_unittests
aarch64-linux-gnu-cross-exe-wrapper out/Release/media_unittests --gtest_filter='V4L2UtilsTest.*' --test-launcher-jobs=1 --single-process-tests
