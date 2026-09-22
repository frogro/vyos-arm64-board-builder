#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee -a /src/vyarm-cross-build.log) 2>&1
trap 'rc=$?; echo "$rc" > /src/vyarm-cross-build.exit; date -u; exit "$rc"' EXIT
if [[ -f /src/vyarm-jobs ]]; then
  VYARM_JOBS=$(cat /src/vyarm-jobs)
fi
VYARM_JOBS=${VYARM_JOBS:-8}
[[ "$VYARM_JOBS" =~ ^(2|4|8)$ ]]
sha256sum -c /src/source-files.sha256
export DEB_BUILD_PROFILES=cross
export DEB_BUILD_OPTIONS="parallel=${VYARM_JOBS:-8} terse"
export HOST_EXEC_WRAPPER=aarch64-linux-gnu-cross-exe-wrapper
eval "$(dpkg-architecture -aarm64 -s)"
export CXXFLAGS_FOR_BUILD='-O2'
export LDFLAGS_FOR_BUILD=''
date -u
file -L /usr/bin/clang-22 /usr/bin/gn /usr/bin/ninja /usr/bin/rustc
printf 'int test(void) { return 42; }\n' >/tmp/arch-test.c
clang-22 --target=aarch64-linux-gnu -c /tmp/arch-test.c -o /tmp/arch-test.o
readelf -h /tmp/arch-test.o
make -f debian/rules override_dh_auto_configure
make -f vyarm-cross.mk vyarm-cross-gen
cp out/Release/args.gn /src/vyarm-cross-args.gn
ninja -C out/Release -t commands obj/media/gpu/v4l2/v4l2/v4l2_video_decoder.o > /src/vyarm-cross-commands.txt
execdate=$(date -u +%FT%TZ)
echo "VYARM_COMPILE_START=$execdate"
ninja -j"${VYARM_JOBS:-8}" -C out/Release chrome chrome_sandbox
echo VYARM_BROWSER_BUILD_COMPLETE
