#!/bin/bash
set -euo pipefail
[[ $(uname -r) == 6.18.50-vyos-f-test4-av1-iommu ]]
bash /config/kiosk-test/kernel-test4/preflight.sh
for n in fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ ! -d $d ]] || echo vyarm-av1-test-block > "$d/driver_override"
done
echo STAGE_LOAD_BEGIN
printf '<6>AV1_STAGE_LOAD_BEGIN\n' > /dev/kmsg
sync
modprobe hantro_vpu vyarm_test_remove_reset_mask=3
echo STAGE_LOAD_RETURNED
printf '<6>AV1_STAGE_LOAD_RETURNED\n' > /dev/kmsg
find /sys/devices/platform/fdc70000.video-codec -maxdepth 3 -name 'video*' -o -name 'media*'
sync
# Deliberately do not unload here: removal is a separate observed stage.
