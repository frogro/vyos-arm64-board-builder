#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee /src/vyarm-p010-unit-fixed.log) 2>&1
trap 'rc=$?; echo "$rc" > /src/vyarm-p010-unit-fixed.exit; date -u; exit "$rc"' EXIT
cp media/gpu/v4l2/v4l2_utils_unittest.cc /src/baseline-color-20260922/v4l2_utils_unittest.p010-before-modifier.cc
cp /src/vyarm-modifier-tests.cc media/gpu/v4l2/v4l2_utils_unittest.cc
python3 - <<'MANIFEST'
import pathlib,hashlib
p=pathlib.Path('source-files.sha256');name='media/gpu/v4l2/v4l2_utils_unittest.cc'
lines=[x for x in p.read_text().splitlines() if not x.endswith('  '+name)]
lines.append(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()+'  '+name)
p.write_text('\n'.join(lines)+'\n')
MANIFEST
export DEB_BUILD_PROFILES=cross
export DEB_BUILD_OPTIONS='parallel=8 terse'
export HOST_EXEC_WRAPPER=aarch64-linux-gnu-cross-exe-wrapper
eval "$(dpkg-architecture -aarm64 -s)"
export CXXFLAGS_FOR_BUILD='-O2'
export LDFLAGS_FOR_BUILD=''
ninja -j8 -C out/Release media_unittests
aarch64-linux-gnu-cross-exe-wrapper out/Release/media_unittests --gtest_filter='V4L2UtilsTest.*' --test-launcher-jobs=1 --single-process-tests
