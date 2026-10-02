#!/bin/bash
set -euo pipefail
bash /work/enable-native-pack.sh
mkdir -p /work/native-pack-test/source
cp /work/native-pack/* /work/native-pack-test/source/
mksquashfs /work/native-pack-test/source /work/native-pack-test/test.squashfs -comp xz -processors 4 -noappend
unsquashfs -d /work/native-pack-test/extracted /work/native-pack-test/test.squashfs
diff -r /work/native-pack-test/source /work/native-pack-test/extracted
echo NATIVE_SQUASHFS_ROUNDTRIP_OK
