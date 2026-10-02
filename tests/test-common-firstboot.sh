#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# The finalizer patches the native timezone handler shipped by vyos-1x.
seed_timezone() {
    mkdir -p "$1/etc" "$1/usr/lib/aarch64-linux-gnu"
    printf 'hosts: files dns #myhostname\n' > "$1/etc/nsswitch.conf"
    touch "$1/usr/lib/aarch64-linux-gnu/libnss_myhostname.so.2"
    mkdir -p "$1/usr/share/vyos/templates/login"
    cp "$1/etc/nsswitch.conf" "$1/usr/share/vyos/templates/login/nsswitch.conf.j2"
    mkdir -p "$1/usr/libexec/vyos/conf_mode"
    printf "def apply():\n        tmp = systemd_services['syslog']\n        call(f'systemctl restart {tmp}')\n" > "$1/usr/libexec/vyos/conf_mode/system_host-name.py"
    mkdir -p "$1/usr/libexec/vyos/conf_mode"
    printf "def apply(tz):\n    call('systemctl restart rsyslog')\n" > "$1/usr/libexec/vyos/conf_mode/system_timezone.py"
}

ROOTFS="$WORK/rootfs"
mkdir -p "$ROOTFS"
seed_timezone "$ROOTFS"

STAGE="$ROOTFS/usr/local/share/vyos-arm64-firstboot"

bash "$ROOT/tools/finalize-vyos-rootfs.sh" test-board "$ROOTFS" no no base

python3 - "$ROOTFS/usr/share/vyos-arm64-board-builder/profile.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["profile"] == "base"
assert data["features"] == {
    "extended_network": False,
    "tailscale_subnet_router": False,
    "kvm_over_ip": False,
}
PY

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    test -x "$STAGE/$script"
done

test -f "$STAGE/setup-transaction.sh"
test -f "$STAGE/set-utf8-locale.py"
grep -qx 'LANG=C.UTF-8' "$ROOTFS/etc/environment"
test -f "$STAGE/modem-services.sh"
test -f "$STAGE/modem-native-wwan.sh"
test -f "$ROOTFS/etc/systemd/system/vyos-modem-restore.service"
test -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-modem-restore.service"
test -x "$ROOTFS/usr/local/sbin/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"
test -x "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
test ! -e "$ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"
test ! -e "$ROOTFS/usr/local/sbin/tailscale"
test ! -e "$ROOTFS/usr/local/sbin/vyos-arm64-kvm-readiness"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.service"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.timer"
test -f "$ROOTFS/etc/systemd/system/vyos-arm64-grow-persistence.service"
test ! -e "$ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
test -L "$ROOTFS/etc/systemd/system/timers.target.wants/vyos-arm64-dhcp-wan-firstboot.timer"
test -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-grow-persistence.service"
test ! -e "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-tailscaled.service"

TAILSCALE_ROOTFS="$WORK/tailscale-rootfs"
mkdir -p "$TAILSCALE_ROOTFS"
seed_timezone "$TAILSCALE_ROOTFS"
bash "$ROOT/tools/finalize-vyos-rootfs.sh" test-board "$TAILSCALE_ROOTFS" yes no tailscale

python3 - "$TAILSCALE_ROOTFS/usr/share/vyos-arm64-board-builder/profile.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["profile"] == "tailscale"
assert data["features"]["tailscale_subnet_router"] is True
PY

if bash "$ROOT/tools/finalize-vyos-rootfs.sh" \
    test-board "$WORK/invalid-rootfs" yes no base >/dev/null 2>&1
then
    echo "ERROR: mismatched build profile was accepted" >&2
    exit 1
fi

KVM_ROOTFS="$WORK/kvm-rootfs"
mkdir -p "$KVM_ROOTFS"
seed_timezone "$KVM_ROOTFS"
bash "$ROOT/tools/finalize-vyos-rootfs.sh" \
    test-board "$KVM_ROOTFS" no no kvm yes
test -x "$KVM_ROOTFS/usr/local/sbin/vyos-arm64-kvm-readiness"
test -d "$KVM_ROOTFS/config/kvm-over-ip"
test -L "$KVM_ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-kvm-gadget-cleanup.service"
test ! -e "$ROOTFS/etc/systemd/system/vyos-kvm-gadget-cleanup.service"
grep -q 'try-restart rsyslog' "$ROOTFS/usr/libexec/vyos/conf_mode/system_timezone.py"
python3 - "$KVM_ROOTFS/usr/share/vyos-arm64-board-builder/profile.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
assert data["profile"] == "kvm"
assert data["features"]["kvm_over_ip"] is True
PY

test -x "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"
test -x "$TAILSCALE_ROOTFS/usr/local/sbin/tailscale"
test -f "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
test -L "$TAILSCALE_ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-tailscaled.service"

grep -Fq 'ConditionFileIsExecutable=/usr/libexec/tailscale/tailscaled' \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
grep -Fq -- '--state=/config/tailscale/state/tailscaled.state' \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
grep -Fq 'Read-only runtime audit' \
    "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness"

grep -Fq '/usr/lib/live/mount/persistence' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'resizepart "$PARTITION_NUMBER" 100%' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'resize2fs "$SOURCE"' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq '"$device_sysfs/partition"' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"
grep -Fq 'findmnt -n -o FSTYPE' \
    "$ROOTFS/usr/local/sbin/vyos-arm64-grow-persistence.sh"

grep -Fq 'SSID="${SSID:-VyOS-AP}"' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq 'PASSPHRASE="${PASSPHRASE:-vyosvyos}"' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$STAGE/ap-dhcp-wan-setup.sh"
grep -Fq '/config/vyos-ap-interface.conf' \
    "$STAGE/modem-connect.sh"

if grep -RqiE \
    'frogro/vyos-build-pi5|UPDATE_CHECK_URL|Photobooth|PHOTOBOOTH' \
    "$STAGE" \
    "$ROOTFS/usr/local/sbin" \
    "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot."*
then
    echo "ERROR: board-specific branding or update channel remains" >&2
    exit 1
fi

if grep -qiE \
    'authkey|192\.168\.|10\.3\.|--advertise-routes' \
    "$TAILSCALE_ROOTFS/usr/local/sbin/vyos-arm64-tailscale-readiness" \
    "$TAILSCALE_ROOTFS/usr/local/sbin/tailscale" \
    "$TAILSCALE_ROOTFS/etc/systemd/system/vyos-arm64-tailscaled.service"
then
    echo "ERROR: Tailscale preparation contains identity or route policy" >&2
    exit 1
fi

echo "PASS: common ARM64 first-boot rootfs contract"

# An upgrade retains the first-boot marker but has a new home directory.
# Helper publication must work independently and never execute setup scripts.
LINK_TEST="$WORK/setup-links-test"
mkdir -p "$LINK_TEST/bin" "$LINK_TEST/home" "$LINK_TEST/stage" "$LINK_TEST/config"
touch "$LINK_TEST/config/.dhcp-wan-ssh-firstboot-done"
touch "$LINK_TEST/home/.profile" "$LINK_TEST/home/.bashrc"
cat > "$LINK_TEST/bin/getent" <<EOF_GETENT
#!/bin/sh
printf '%s\n' 'vyos:x:$(id -u):$(id -g):test:$LINK_TEST/home:/bin/bash'
EOF_GETENT
chmod +x "$LINK_TEST/bin/getent"
for script in ap-dhcp-wan-setup.sh dhcp-wan-ssh-setup.sh modem-connect.sh set-locales.sh; do
    printf '#!/bin/sh\nexit 99\n' > "$LINK_TEST/stage/$script"
    chmod +x "$LINK_TEST/stage/$script"
done
python3 - "$ROOT/tools/common-firstboot/vyos-arm64-setup-links.sh" "$LINK_TEST" <<'PY_LINKS'
from pathlib import Path
import sys
source, root = map(Path, sys.argv[1:])
(root/'setup-links.sh').write_text(source.read_text().replace('/usr/local/share/vyos-arm64-firstboot', str(root/'stage')))
PY_LINKS
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
for script in ap-dhcp-wan-setup.sh modem-connect.sh set-locales.sh; do
    test "$(readlink "$LINK_TEST/home/$script")" = "$LINK_TEST/stage/$script"
done
# Repeated boots preserve custom files and custom/dangling links.
rm "$LINK_TEST/home/modem-connect.sh" "$LINK_TEST/home/set-locales.sh"
printf 'custom\n' > "$LINK_TEST/home/modem-connect.sh"
ln -s /nonexistent/user-script "$LINK_TEST/home/set-locales.sh"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
grep -qx custom "$LINK_TEST/home/modem-connect.sh"
test "$(readlink "$LINK_TEST/home/set-locales.sh")" = /nonexistent/user-script
test -L "$ROOTFS/etc/systemd/system/multi-user.target.wants/vyos-arm64-setup-links.service"
test -x "$ROOTFS/usr/local/sbin/vyos-arm64-setup-links.sh"
! grep -q ConditionPathExists "$ROOTFS/etc/systemd/system/vyos-arm64-setup-links.service"
grep -Fq 'ConditionPathExists=!/config/.dhcp-wan-ssh-firstboot-done' "$ROOTFS/etc/systemd/system/vyos-arm64-dhcp-wan-firstboot.service"
grep -Fq 'SETUP="$STAGE/dhcp-wan-ssh-setup.sh"' "$ROOTFS/usr/local/sbin/vyos-arm64-dhcp-wan-firstboot-wrapper.sh"

# A fresh image has no login user until the initial VyOS commit completes.
mv "$LINK_TEST/bin/getent" "$LINK_TEST/bin/getent-ready"
cat > "$LINK_TEST/bin/getent" <<EOF_DELAY
#!/bin/bash
if [[ ! -e "$LINK_TEST/user-ready" ]]; then
    touch "$LINK_TEST/user-ready"
    exit 2
fi
exec "$LINK_TEST/bin/getent-ready" "\$@"
EOF_DELAY
chmod +x "$LINK_TEST/bin/getent"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
test -e "$LINK_TEST/user-ready"

ln -s "$LINK_TEST/stage/dhcp-wan-ssh-setup.sh" "$LINK_TEST/home/dhcp-wan-ssh-setup.sh"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
test ! -L "$LINK_TEST/home/dhcp-wan-ssh-setup.sh"
printf 'user script\n' > "$LINK_TEST/home/dhcp-wan-ssh-setup.sh"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
grep -qx 'user script' "$LINK_TEST/home/dhcp-wan-ssh-setup.sh"

# Board-scoped helper: finalizer is shared by install images and update ISOs.
test ! -e "$STAGE/setup-lan-ap-bridge.sh"
OP_ROOTFS="$WORK/orangepi-rootfs"
seed_timezone "$OP_ROOTFS"
bash "$ROOT/tools/finalize-vyos-rootfs.sh" orangepi5-plus "$OP_ROOTFS" no no base
test -x "$OP_ROOTFS/usr/local/share/vyos-arm64-firstboot/setup-lan-ap-bridge.sh"
test ! -e "$LINK_TEST/home/setup-lan-ap-bridge.sh"
cp "$OP_ROOTFS/usr/local/share/vyos-arm64-firstboot/setup-lan-ap-bridge.sh" "$LINK_TEST/stage/"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
test "$(readlink "$LINK_TEST/home/setup-lan-ap-bridge.sh")" = "$LINK_TEST/stage/setup-lan-ap-bridge.sh"
rm "$LINK_TEST/home/setup-lan-ap-bridge.sh"
printf 'custom bridge\n' > "$LINK_TEST/home/setup-lan-ap-bridge.sh"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
grep -qx 'custom bridge' "$LINK_TEST/home/setup-lan-ap-bridge.sh"
echo 'PASS: Orange Pi bridge helper scope and user-file preservation'
# passwd can be visible before useradd initializes the home. Do not win that race.
RACE_HOME="$LINK_TEST/race-home"
cat > "$LINK_TEST/bin/getent" <<EOF_RACE
#!/bin/sh
printf '%s\n' 'vyos:x:$(id -u):$(id -g):test:$RACE_HOME:/bin/bash'
EOF_RACE
cat > "$LINK_TEST/bin/sleep" <<EOF_SEED
#!/bin/sh
test ! -e "$RACE_HOME" || exit 42
mkdir "$RACE_HOME"
touch "$RACE_HOME/.profile" "$RACE_HOME/.bashrc"
EOF_SEED
chmod +x "$LINK_TEST/bin/getent" "$LINK_TEST/bin/sleep"
PATH="$LINK_TEST/bin:$PATH" bash "$LINK_TEST/setup-links.sh"
test -f "$RACE_HOME/.bashrc"
test -L "$RACE_HOME/set-locales.sh"
echo "PASS: helper publication waits for useradd skeleton initialization"
