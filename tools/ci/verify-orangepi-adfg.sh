#!/bin/bash
set -euo pipefail
case "$BOARD" in rock-5b|orangepi5-plus) ;; *) exit 1 ;; esac
image=${1:?Image required}
loop=$(losetup --find --show --read-only --partscan "$image")
verify=$(mktemp -d)
trap 'mountpoint -q "$verify/mnt" && umount "$verify/mnt"; losetup -d "$loop"; rm -rf "$verify"' EXIT
mkdir "$verify/mnt"
udevadm settle
mount -o ro "${loop}p3" "$verify/mnt"
squash=$(find "$verify/mnt/boot" -name '*.squashfs' -print -quit)
[[ -s $squash ]]
unsquashfs -cat "$squash" usr/share/vyos-arm64-board-builder/receiver-runtime/runtime.json > "$verify/g.json"
unsquashfs -cat "$squash" usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.json > "$verify/f.json"
unsquashfs -cat "$squash" usr/share/vyos-arm64-board-builder/kvm-gadget-provider.env > "$verify/gadget.env"
source "$verify/gadget.env"
if [[ $BOARD == orangepi5-plus ]]; then
 [[ "$KVM_GADGET_DEFAULT_PORT" == usbc && "$KVM_GADGET_UDC_USBC" == fc000000.usb ]]
 ! grep -q fc400000 "$verify/gadget.env"
else
 [[ "$KVM_GADGET_DEFAULT_PORT" == dedicated && "$KVM_GADGET_UDC_DEDICATED" == fc400000.usb ]]
fi
python3 - "$verify" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(sys.argv[1]);g=json.loads((p/'g.json').read_text());f=json.loads((p/'f.json').read_text())
assert g['source_commit']==os.environ['GITHUB_SHA']
assert f['builder_commit']==os.environ['GITHUB_SHA']
assert f['sunshine_direct_rga_available']
PY
for path in \
 usr/lib/python3/dist-packages/vyos/receiver.py \
 usr/libexec/vyos/vyos-kvm-cached-launch \
 usr/libexec/vyos/conf_mode/service_kvm_over_ip.py \
 opt/vyatta/share/vyatta-cfg/templates/container/name/node.tag/receiver/method/node.def \
 opt/vyatta/share/vyatta-cfg/templates/container/name/node.tag/kiosk/rotation/node.def; do
 unsquashfs -cat "$squash" "$path" > /dev/null
done
python3 - <<'PY'
import json,os,pathlib
p=pathlib.Path('work/build')/os.environ['BOARD']/'selection/feature-profile.json'
m=json.loads(p.read_text())
assert all(m['features'][f] for f in ['extended_network','tailscale_subnet_router','kvm_over_ip','kiosk_f','receiver_g'])
PY
