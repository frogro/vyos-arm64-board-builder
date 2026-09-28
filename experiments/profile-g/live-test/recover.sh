#!/bin/bash
# Host service only: never reset the management radio in an SSH foreground job.
set -Eeuo pipefail
root=${PROFILE_G_TEST_ROOT:-/config/receiver/g-live-20260928}
if [[ ${1:-} != --service ]]; then
    exec systemctl start --no-block profile-g-recovery.service
fi
exec >> "$root/recovery-v2.log" 2>&1
exec 9>/run/profile-g-recovery.lock
flock -n 9 || exit 0
trap 'echo "$(date -Is) recovery failed at line $LINENO"' ERR
echo "$(date -Is) recovery begin"
healthy() {
    systemctl is-active --quiet hostapd@wlan0.service &&
    iw dev wlan0 info | grep -q 'type AP' &&
    python3 - "$root" <<'PY'
import json,subprocess,sys
old=json.load(open(sys.argv[1]+'/backup/wlan0-address.json'))[0]
now=json.loads(subprocess.check_output(['ip','-j','address','show','dev','wlan0']))[0]
wanted={(a['local'],a['prefixlen']) for a in old['addr_info'] if a['family']=='inet'}
actual={(a['local'],a['prefixlen']) for a in now['addr_info'] if a['family']=='inet'}
mac=open(sys.argv[1]+'/backup/wlan0-mac').read().strip().lower()
assert wanted and wanted <= actual and now['address'].lower()==mac and 'UP' in now['flags']
PY
}
if podman container exists receiver-g-test; then
    timeout 30 podman stop -t 8 receiver-g-test
fi
if healthy; then
    echo 'AP already restored; radio left untouched'
else
    systemctl stop hostapd@wlan0.service
    ip link set wlan0 down
    ip link set wlan0 address "$(cat "$root/backup/wlan0-mac")"
    iw dev wlan0 set type managed
    python3 - "$root" <<'PY'
import json,subprocess,sys
for a in json.load(open(sys.argv[1]+'/backup/wlan0-address.json'))[0]['addr_info']:
    if a['family']=='inet':
        subprocess.run(['ip','address','replace',a['local']+'/'+str(a['prefixlen']),'dev','wlan0'],check=True)
PY
    ip link set wlan0 up
    systemctl restart hostapd@wlan0.service
fi
systemctl start vyos-container-kiosk.service
systemctl start vyos-kiosk-inputs-kiosk.service vyos-kiosk-sunshine-inputs-kiosk.service
for n in {1..15}; do
    if healthy && systemctl is-active --quiet vyos-container-kiosk.service; then
        echo "$(date -Is) recovery verified"
        systemctl stop profile-g-recovery.timer
        exit 0
    fi
    sleep 1
done
exit 1
