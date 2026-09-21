#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee -a /src/vyarm-build-nv15.log) 2>&1
trap 'rc=$?; printf "VYARM_BUILD_EXIT=%s\n" "$rc"; exit "$rc"' EXIT
printf 'VYARM_BUILD_START '; date -u
export DEB_BUILD_OPTIONS=parallel=1
make -f debian/rules -f vyarm-regenerate.mk vyarm-regenerate
/src/vyarm-native-tools/ld-linux-x86-64.so.2 --library-path /src/vyarm-native-tools /src/vyarm-native-tools/ninja -j1 -C out/Release chrome chrome_sandbox
printf 'VYARM_BROWSER_BUILD_COMPLETE\n'
