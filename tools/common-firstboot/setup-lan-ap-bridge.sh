#!/bin/vbash
# Orange Pi: eth1 + wlan0 -> br0, existing 10.3.141.0/24 AP network.
# Default: show candidate changes only. --apply: commit and save.
set -o pipefail
export PATH="$PATH:/usr/sbin:/sbin"
export LANG=C.UTF-8 LC_ALL=C.UTF-8
case "${1:---check}" in --check|--apply) MODE="${1:---check}";; *) echo 'Usage: setup-lan-ap-bridge.sh [--check|--apply]'; builtin exit 2;; esac
[ "$(id -u)" -ne 0 ] || { echo 'Run as vyos, without sudo.'; builtin exit 1; }
if [ "$(id -g -n)" != vyattacfg ]; then
    printf -v bridge_cmd '%q ' /bin/vbash "$(readlink -f "$0")" "$MODE"
    exec sg vyattacfg -c "$bridge_cmd"
fi
if [ "$(readlink -f /proc/$$/exe)" != "$(readlink -f /bin/vbash)" ]; then
    exec /bin/vbash "$(readlink -f "$0")" "$MODE"
fi
# Refuse an unexpected configuration instead of rewriting another LAN or firewall.
BRIDGE_STATE="$(python3 - <<'PY'
import subprocess, shlex
lines=subprocess.check_output(['/opt/vyatta/bin/vyatta-op-cmd-wrapper','show','configuration','commands'],text=True)
c=[shlex.split(x) for x in lines.splitlines() if x.startswith('set ')]
def values(prefix):
    p=shlex.split('set '+prefix)
    return [x[len(p):] for x in c if x[:len(p)]==p]
def require(prefix, expected):
    if values(prefix)!=expected: raise SystemExit('Unexpected configuration: '+prefix+'; no changes applied.')
bridged=bool(values('interfaces bridge br0'))
if bridged:
    require('interfaces bridge br0 address', [['10.3.141.50/24']])
    if sorted(values('interfaces bridge br0 member interface')) != [['eth1'], ['wlan0']]:
        raise SystemExit('Unexpected br0 members; no changes applied.')
require('interfaces wireless wlan0 address', [] if bridged else [['10.3.141.50/24']])
require('interfaces wireless wlan0 type', [['access-point']])
require('interfaces ethernet eth1 address', [])
if not bridged: require('interfaces bridge', [])
listeners=values('service dhcp-server listen-interface')
if any(x not in [['wlan0'], ['br0']] for x in listeners):
    raise SystemExit('Additional DHCP interfaces configured; review required.')
require('service dhcp-server listen-address', [])
require('service dhcp-server shared-network-name VYOS-AP subnet 10.3.141.0/24 option default-router', [['10.3.141.50']])
if any(x[0]!='VYOS-AP' for x in values('service dhcp-server shared-network-name')):
    raise SystemExit('Additional DHCP networks configured; review required.')
require('firewall ipv4 forward filter rule 20 inbound-interface name', [['br0']] if bridged else [['wlan0']])
require('firewall ipv4 forward filter rule 20 action', [['jump']])
require('firewall ipv4 forward filter rule 20 jump-target', [['VYOS-AP-OUT']])
require('nat source rule 150 outbound-interface name', [['eth0']])
require('nat source rule 150 source address', [['10.3.141.0/24']])
require('nat source rule 150 translation address', [['masquerade']])
# No additional interface-bound firewall rules may be left pointing at wlan0.
for x in c:
    if x[1:2]==['firewall'] and ('wlan0' in x or 'eth1' in x):
        if x!=shlex.split('set firewall ipv4 forward filter rule 20 inbound-interface name wlan0'):
            raise SystemExit('Additional LAN interface firewall reference found; review required.')
print('bridged' if bridged else 'unbridged')
PY
)" || builtin exit 1
echo "Verified AP, DHCP and firewall/NAT; current state: $BRIDGE_STATE"
source /opt/vyatta/etc/functions/script-template
configure || builtin exit 1
[ -n "${VYATTA_CONFIG_TMP:-}" ] && [ -d "$VYATTA_CONFIG_TMP" ] || builtin exit 1
cleanup_bridge() { discard >/dev/null 2>&1 || true; }
before="$(compare)" || builtin exit 1
if [ -n "$before" ] && [ "$before" != 'No changes between working and active configurations.' ]; then
    echo 'Pending candidate changes found; finish the existing configuration session first.'
    builtin exit 1
fi
trap cleanup_bridge EXIT
fail_bridge() { echo 'Configuration command failed; candidate discarded.' >&2; builtin exit 1; }
# One commit moves the L3 address and firewall assignment together.
set interfaces bridge br0 description 'LAN and WiFi AP' || fail_bridge
set interfaces bridge br0 address '10.3.141.50/24' || fail_bridge
set interfaces bridge br0 member interface eth1 || fail_bridge
set interfaces bridge br0 member interface wlan0 || fail_bridge
set interfaces bridge br0 stp || fail_bridge
if [ "$BRIDGE_STATE" = unbridged ]; then
    delete interfaces wireless wlan0 address '10.3.141.50/24' || fail_bridge
fi
# Bind Kea to the L3 bridge, not the addressless member ports.
if cli-shell-api exists service dhcp-server listen-interface wlan0; then
    delete service dhcp-server listen-interface wlan0 || fail_bridge
fi
set service dhcp-server listen-interface br0 || fail_bridge
set firewall ipv4 forward filter rule 20 inbound-interface name 'br0' || fail_bridge
# DHCP, DNS listen address and NAT source subnet stay identical.
changes="$(compare)" || fail_bridge
printf '%s\n' "$changes"
if [ "$MODE" != --apply ]; then
    echo 'CHECK ONLY: candidate discarded. To apply: bash ~/setup-lan-ap-bridge.sh --apply'
    builtin exit 0
fi
if [ -z "$changes" ] || [ "$changes" = 'No changes between working and active configurations.' ]; then
    echo 'Bridge and DHCP binding already configured; no commit or restart needed.'
    ip -br address show br0
    /usr/sbin/bridge link show
    systemctl is-active isc-kea-dhcp4-server
    builtin exit $?
fi
backup="/config/config.boot.before-lan-bridge-$(date +%Y%m%d-%H%M%S)"
sudo cp -p /config/config.boot "$backup" || fail_bridge
echo "Saved configuration backup: $backup"
echo 'Applying bridge. WiFi may briefly disconnect; use SSH through eth0.'
commit || fail_bridge
save /config/config.boot || { echo 'Commit succeeded but save failed; run save before reboot.' >&2; builtin exit 1; }
# Kea retains raw sockets on the former wlan0 interface until restarted.
sudo systemctl restart isc-kea-dhcp4-server || { echo 'Bridge saved, but DHCP restart failed.' >&2; builtin exit 1; }
# STP may need approximately 30 seconds before forwarding after creation.
ready=no
for attempt in {1..40}; do
    if /usr/sbin/bridge link show master br0 | grep -q 'state forwarding'; then ready=yes; break; fi
    sleep 1
done
if [ "$ready" != yes ]; then
    echo 'Bridge saved; no forwarding member yet. Check cable/WiFi and STP state.' >&2
    builtin exit 1
fi
systemctl is-active --quiet isc-kea-dhcp4-server || builtin exit 1
echo 'Bridge committed and saved. Gateway 10.3.141.50; existing DHCP and NAT retained.'
ip -br address show br0
/usr/sbin/bridge link show
