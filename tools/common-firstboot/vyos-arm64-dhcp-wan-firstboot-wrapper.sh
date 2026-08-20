#!/bin/bash
# Run the VyOS configuration script, then restart the DHCP client in its own
# systemd service so it is not terminated when the configuration session ends.

set -euo pipefail

LOG="/config/dhcp-wan-firstboot-wrapper.log"
MARKER="/config/.dhcp-wan-ssh-firstboot-done"
IFACE_FILE="/config/.dhcp-wan-interface"
STAGE="/usr/local/share/vyos-arm64-firstboot"
TIMER="vyos-arm64-dhcp-wan-firstboot.timer"

exec >>"$LOG" 2>&1

log() {
    printf '%s %s\n' "$(date -Is)" "vyos-arm64-dhcp-wan-wrapper: $*"
}

fail() {
    log "FEHLER: $*"
    exit 1
}

[ -e "$MARKER" ] && exit 0

VYOS_ENTRY="$(getent passwd vyos || true)"
[ -n "$VYOS_ENTRY" ] || fail "VyOS-Benutzer ist noch nicht vorhanden; Timer versucht es erneut"

VYOS_UID="$(printf '%s\n' "$VYOS_ENTRY" | awk -F: '{print $3}')"
VYOS_GID="$(printf '%s\n' "$VYOS_ENTRY" | awk -F: '{print $4}')"
HOME_DIR="$(printf '%s\n' "$VYOS_ENTRY" | awk -F: '{print $6}')"

[[ "$VYOS_UID" =~ ^[0-9]+$ ]] || fail "Ungueltige UID fuer den VyOS-Benutzer"
[[ "$VYOS_GID" =~ ^[0-9]+$ ]] || fail "Ungueltige GID fuer den VyOS-Benutzer"
[ -n "$HOME_DIR" ] || fail "Kein Home-Verzeichnis fuer den VyOS-Benutzer"

[ -d "$STAGE" ] || fail "First-Boot-Staging-Verzeichnis fehlt: $STAGE"
install -d -m 0755 -o "$VYOS_UID" -g "$VYOS_GID" "$HOME_DIR"

for script in \
    ap-dhcp-wan-setup.sh \
    dhcp-wan-ssh-setup.sh \
    modem-connect.sh \
    set-locales.sh
do
    [ -r "$STAGE/$script" ] || fail "First-Boot-Hilfsskript fehlt: $STAGE/$script"
    install -m 0755 -o "$VYOS_UID" -g "$VYOS_GID" \
        "$STAGE/$script" "$HOME_DIR/$script"
done

SETUP="$HOME_DIR/dhcp-wan-ssh-setup.sh"

log "Starte VyOS-Konfigurationsskript"

/usr/sbin/runuser -u vyos -- /bin/vbash -lc "$SETUP --auto"

[ -r "$IFACE_FILE" ] || fail "Interface-Datei fehlt: $IFACE_FILE"
IFACE="$(cat "$IFACE_FILE")"
[ -e "/sys/class/net/$IFACE" ] || fail "Interface $IFACE existiert nicht"

log "Konfiguration beendet; starte dhclient@${IFACE}.service ausserhalb der Konfigurationssitzung neu"

/bin/systemctl reset-failed "dhclient@${IFACE}.service" 2>/dev/null || true
/bin/systemctl restart "dhclient@${IFACE}.service"

IPV4=""
for _ in $(seq 1 60); do
    IPV4="$(ip -4 -br address show dev "$IFACE" 2>/dev/null | awk '{print $3; exit}')"
    [ -n "$IPV4" ] && break
    sleep 2
done

[ -n "$IPV4" ] || fail "$IFACE erhielt nach dem dhclient-Neustart keine IPv4-Adresse"
log "$IFACE behaelt IPv4 $IPV4"

DEFAULT_ROUTE=""
for _ in $(seq 1 30); do
    DEFAULT_ROUTE="$(ip -4 route show default dev "$IFACE" 2>/dev/null | head -1)"
    [ -n "$DEFAULT_ROUTE" ] && break
    sleep 2
done

[ -n "$DEFAULT_ROUTE" ] || fail "$IFACE erhielt per DHCP keine IPv4-Default-Route"
log "Default-Route aktiv: $DEFAULT_ROUTE"

if ! ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:|\])22$'; then
    for SSH_UNIT in ssh@default.service ssh.service sshd.service; do
        if /bin/systemctl cat "$SSH_UNIT" >/dev/null 2>&1; then
            /bin/systemctl restart "$SSH_UNIT" || true
            break
        fi
    done
fi

for _ in $(seq 1 30); do
    if ss -ltnH 2>/dev/null | awk '{print $4}' | grep -Eq '(^|:|\])22$'; then
        touch "$MARKER"
        chmod 600 "$MARKER"
        log "FERTIG: $IFACE=$IPV4, DHCP-Client aktiv, SSH lauscht auf Port 22"
        /bin/systemctl disable --now "$TIMER" >/dev/null 2>&1 || true
        exit 0
    fi
    sleep 1
done

fail "SSH lauscht nicht auf Port 22"
