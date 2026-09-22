#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee /src/vyarm-p010-incremental.log) 2>&1
trap 'rc=$?; echo "$rc" > /src/vyarm-p010-incremental.exit; date -u; exit "$rc"' EXIT
mkdir /src/baseline-color-20260922
cp --reflink=auto out/Release/chrome out/Release/chrome_sandbox out/Release/args.gn source-files.sha256 media/gpu/v4l2/v4l2_utils.cc media/gpu/v4l2/v4l2_utils_unittest.cc /src/baseline-color-20260922/
sha256sum out/Release/chrome > /src/baseline-color-20260922/browser.sha256
printf '%s  %s\n' 3f423badc17f89e3e2a2633de13eaba76e77a34cb4754e4e2571468673b42a98 media/gpu/v4l2/v4l2_utils.cc | sha256sum -c -
printf '%s  %s\n' f2e96df5531d3ee9c37603805612acc7760b3d495d35a2b72fd19e0c2d243b6f media/gpu/v4l2/v4l2_utils_unittest.cc | sha256sum -c -
cp /src/vyarm-v4l2_utils.cc media/gpu/v4l2/v4l2_utils.cc
cp /src/vyarm-v4l2_utils_unittest.cc media/gpu/v4l2/v4l2_utils_unittest.cc
python3 - <<'MANIFEST'
import hashlib,pathlib
p=pathlib.Path('source-files.sha256');lines=p.read_text().splitlines()
for name in ['media/gpu/v4l2/v4l2_utils.cc','media/gpu/v4l2/v4l2_utils_unittest.cc']:
 lines=[x for x in lines if not x.endswith('  '+name)]
 lines.append(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()+'  '+name)
p.write_text('\n'.join(lines)+'\n')
MANIFEST
sha256sum -c source-files.sha256
export DEB_BUILD_PROFILES=cross
export DEB_BUILD_OPTIONS='parallel=8 terse'
export HOST_EXEC_WRAPPER=aarch64-linux-gnu-cross-exe-wrapper
eval "$(dpkg-architecture -aarm64 -s)"
export CXXFLAGS_FOR_BUILD='-O2'
export LDFLAGS_FOR_BUILD=''
date -u
ninja -j8 -C out/Release chrome chrome_sandbox
sha256sum out/Release/chrome
echo VYARM_P010_INCREMENTAL_COMPLETE
