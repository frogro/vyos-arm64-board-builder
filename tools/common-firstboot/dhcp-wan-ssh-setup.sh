#!/bin/vbash
# Configure only wired DHCP WAN and SSH in VyOS.
# No AP, DHCP server, DNS forwarding, NAT, or modem configuration.

set -o pipefail
# Non-login SSH invocations may omit administrative program directories.
export PATH="${PATH}:/usr/sbin:/sbin"

AUTO_SETUP=no
WIRED_IF="${WIRED_IF:-auto}"
ROUTE_DISTANCE="${ROUTE_DISTANCE:-1}"
LOG="/config/dhcp-wan-ssh-setup.log"
IFACE_FILE="/config/.dhcp-wan-interface"

log() {
    printf '%s %s\n' "$(date -Is)" "dhcp-wan-ssh-setup: $*" | tee -a "$LOG"
}

fail() {
    log "ERROR: $*"
    builtin exit 1
}

# VyOS configuration scripts must run with the vyattacfg primary group.
# Re-exec before argument parsing so all CLI arguments are preserved.
if [ "$(id -g -n)" != "vyattacfg" ] && [ "${VYOS_ARM64_VYATTACFG_REEXEC:-0}" != "1" ]; then
    command -v sg >/dev/null 2>&1 || fail "sg command is missing"
    SCRIPT_PATH="$(readlink -f "$0")"
    printf -v SCRIPT_Q '%q' "$SCRIPT_PATH"
    ARGS_Q=""
    for ARG in "$@"; do
        printf -v ARG_Q '%q' "$ARG"
        ARGS_Q+=" $ARG_Q"
    done
    export VYOS_ARM64_VYATTACFG_REEXEC=1
    exec sg vyattacfg -c "/bin/vbash $SCRIPT_Q$ARGS_Q"
fi

for ARG in "$@"; do
    case "$ARG" in
        --auto) AUTO_SETUP=yes ;;
        --interface=*) WIRED_IF="${ARG#*=}" ;;
        --distance=*) ROUTE_DISTANCE="${ARG#*=}" ;;
        -h|--help)
            echo "dhcp-wan-ssh-setup.sh [--auto] [--interface=eth0] [--distance=1]"
            builtin exit 0
            ;;
        *) fail "Unbekannter Parameter: $ARG" ;;
    esac
done

detect_wired_interface() {
    local CANDIDATE

    for CANDIDATE in /sys/class/net/eth* /sys/class/net/en*; do
        [ -e "$CANDIDATE" ] || continue
        CANDIDATE="${CANDIDATE##*/}"
        [ -e "/sys/class/net/$CANDIDATE/device" ] || continue
        [ -r "/sys/class/net/$CANDIDATE/address" ] || continue
        printf '%s\n' "$CANDIDATE"
        return 0
    done

    return 1
}

if [ "$WIRED_IF" = "auto" ]; then
    WIRED_IF="$(detect_wired_interface || true)"
fi

[ -n "$WIRED_IF" ] || fail "No wired Ethernet interface detected"
[ -e "/sys/class/net/$WIRED_IF" ] || fail "Interface $WIRED_IF does not exist"

MAC="$(tr '[:upper:]' '[:lower:]' < "/sys/class/net/$WIRED_IF/address" 2>/dev/null)"
printf '%s\n' "$MAC" | grep -Eq '^([0-9a-f]{2}:){5}[0-9a-f]{2}$' ||
    fail "Invalide MAC-Adresse fuer $WIRED_IF: ${MAC:-leer}"

case "$ROUTE_DISTANCE" in
    ''|*[!0-9]*) fail "Invalide Routendistanz: $ROUTE_DISTANCE" ;;
esac

printf '%s\n' "$WIRED_IF" > "$IFACE_FILE"
chmod 600 "$IFACE_FILE"

log "Detected: interface=$WIRED_IF MAC=$MAC DHCP route distance=$ROUTE_DISTANCE"

sudo /sbin/ip link set "$WIRED_IF" up 2>/dev/null || true

[ -r /opt/vyatta/etc/functions/script-template ] ||
    fail "VyOS script-template is missing"

source /opt/vyatta/etc/functions/script-template
source "$(dirname "$(readlink -f "$0")")/setup-transaction.sh"
configure || { echo "ERROR: Cannot enter configuration mode." >&2; builtin exit 1; }

setup_set interfaces ethernet "$WIRED_IF" description 'WAN-LAN-DHCP'
setup_set interfaces ethernet "$WIRED_IF" address 'dhcp'
setup_set interfaces ethernet "$WIRED_IF" dhcp-options default-route-distance "$ROUTE_DISTANCE"
setup_set service ssh

# Seed only fresh installations; never overwrite an administrator's channel.
CHANNEL_FILE=/usr/share/vyos-arm64-board-builder/update-channel.json
if [[ "$AUTO_SETUP" == yes && ! -e /config/.dhcp-wan-ssh-firstboot-done && -r "$CHANNEL_FILE" ]]; then
    if ! "$API" existsActive system update-check url; then
        CHANNEL_URL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["url"])' "$CHANNEL_FILE")" || fail "Invalid image update channel"
        setup_set system update-check url "$CHANNEL_URL"
    fi
fi

if ! setup_commit_save; then
    discard 2>/dev/null || true
    fail "Could not commit and save wired WAN configuration"
fi
log "VyOS configuration saved (or already present)"

log "Konfigurationsphase abgeschlossen"
