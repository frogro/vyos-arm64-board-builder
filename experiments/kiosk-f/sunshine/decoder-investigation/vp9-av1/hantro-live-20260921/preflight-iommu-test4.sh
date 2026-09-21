#!/usr/bin/env bash
# Read-only guard, to run on the ROCK AFTER the isolated one-shot boot.
set -euo pipefail
expected=6.18.50-vyos-f-test4-av1-iommu
[[ $(uname -r) == "$expected" ]] || { echo "Wrong kernel: $(uname -r); expected $expected" >&2; exit 2; }
av1=/sys/bus/platform/devices/fdc70000.video-codec
iommu=/sys/bus/platform/devices/fdca0000.iommu
[[ -d "$av1" && -d "$iommu" ]]
[[ -L "$iommu/driver" ]] || { echo 'AV1 IOMMU did not bind' >&2; exit 3; }
[[ $(basename "$(readlink -f "$iommu/driver")") == vsi_iommu ]]
[[ ! -d /sys/module/hantro_vpu ]] || { echo 'Hantro already loaded; do not disturb it' >&2; exit 4; }
for n in fdc70000 fdb50000 fdba0000 fdba4000 fdba8000 fdbac000; do
 d=/sys/bus/platform/devices/$n.video-codec
 [[ -d "$d" ]] || continue
 [[ ! -L "$d/driver" && $(cat "$d/driver_override") == '(null)' ]] || { echo "Device $n already claimed/overridden" >&2; exit 5; }
done
modinfo -F vermagic hantro_vpu | grep -q "^$expected "
modinfo -F parm hantro_vpu | grep -q '^vyarm_test_remove_reset_mask:'
printf 'IOMMU driver: %s\n' "$(readlink -f "$iommu/driver")"
printf 'AV1 IOMMU group (may appear only on decoder attach): '
readlink -f "$av1/iommu_group" || true
printf 'IOMMU runtime status: '
cat "$iommu/power/runtime_status"
grep -E 'MemAvailable|CmaTotal|CmaFree' /proc/meminfo
printf 'PREFLIGHT_OK: no modules loaded, no settings changed\n'
