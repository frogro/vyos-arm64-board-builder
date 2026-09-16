# Image-owned service templates. Sourced by modem-connect.sh.
modem_needs_unlock() {
  [ ! -r "$CONFIG_FILE" ] || ! grep -qx 'UNLOCK_KIND=none' "$CONFIG_FILE"
}

write_unlock_service_unit() {
  if ! modem_needs_unlock; then
    systemctl disable modem-unlock.service >/dev/null 2>&1 || true
    rm -f "$UNLOCK_SERVICE_PATH"
    return 0
  fi
  cat > "$UNLOCK_SERVICE_PATH" <<EOF
[Unit]
Description=Prepare modem FCC unlock only when required
After=vyos-router.service systemd-modules-load.service systemd-udev-trigger.service
Requires=vyos-router.service
RequiresMountsFor=/config
Before=modem-connect.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=${SELF_PATH} --service-run --unlock-only
RemainAfterExit=yes
TimeoutStartSec=600
Restart=on-failure
RestartSec=15
StandardInput=null

[Install]
WantedBy=multi-user.target
EOF
}

write_service_unit() {
  local unlock_dependency=""
  modem_needs_unlock && unlock_dependency="modem-unlock.service"
  cat > "$SERVICE_PATH" <<EOF
[Unit]
Description=Automatically connect the modem and configure the VyOS WWAN fallback
After=vyos-router.service systemd-modules-load.service systemd-udev-trigger.service ${unlock_dependency} network.target
Requires=vyos-router.service ${unlock_dependency}
StartLimitIntervalSec=0

[Service]
Type=oneshot
ExecStart=${SELF_PATH} --service-run
RemainAfterExit=yes
TimeoutStartSec=600
Restart=on-failure
RestartSec=20
StandardInput=null

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable modem-connect.service >/dev/null 2>&1
  if modem_needs_unlock; then
    systemctl enable modem-unlock.service >/dev/null 2>&1
  else
    # Drop the old dependency before stopping an obsolete unlock unit.
    systemctl stop modem-unlock.service >/dev/null 2>&1 || true
    systemctl reset-failed modem-unlock.service >/dev/null 2>&1 || true
  fi
}

write_failover_service_unit() {
  # Generic WAN failover monitor. It does not know or care whether the modem is
  # FM350, QMI, MBIM, ModemManager, ECM/NCM/RNDIS or PPP. modem-connect writes
  # the current modem interface/gateway to ROUTE_CACHE. The monitor keeps routing
  # preference correct and may request a controlled modem-connect restart when
  # liveness/state/data-path checks fail; it never performs a VyOS commit itself.
  cat > "$FAILOVER_SCRIPT_PATH" <<'FAILOVER_EOF'
#!/bin/bash
set -u

CONFIG_FILE="${CONFIG_FILE:-/config/modem-connect/modem-connect.conf}"
ROUTE_CACHE="${ROUTE_CACHE:-/config/modem-connect/modem-route.conf}"
WIRED_METRIC="${WIRED_DEFAULT_METRIC:-20}"
DEFAULT_WWAN_METRIC="${WWAN_ROUTE_METRIC:-200}"
POLL_SEC="${FAILOVER_POLL_SEC:-2}"
NOIP_ATTEMPTS="${WWAN_NOIP_ATTEMPTS:-4}"
RECOVERY_COOLDOWN="${WWAN_RECOVERY_COOLDOWN:-60}"
CONNECT_GRACE="${WWAN_CONNECT_GRACE:-60}"
DATA_HEALTH_INTERVAL="${WWAN_DATA_HEALTH_INTERVAL:-15}"
DATA_HEALTH_FAILURES="${WWAN_DATA_HEALTH_FAILURES:-3}"
DATA_HEALTH_TARGET="${WWAN_DATA_HEALTH_TARGET:-1.1.1.1}"
DATA_HEALTH_PINGS="${WWAN_DATA_HEALTH_PINGS:-3}"
MM_ALWAYS_CONNECTED="${MM_ALWAYS_CONNECTED:-1}"
MM_STATE_FAILURES="${MM_STATE_FAILURES:-2}"
noip_count=0
health_fail_count=0
mm_state_fail_count=0
last_health_check=0
last_recovery=0

log() { logger -t modem-wan-failover -- "$*"; }

cfg_get() {
  local f="$1" k="$2"
  [ -r "$f" ] || return 0
  sed -n "s/^${k}=//p" "$f" 2>/dev/null | head -1
}

net_driver() {
  local iface="$1" p
  p="$(readlink -f "/sys/class/net/$iface/device/driver" 2>/dev/null || true)"
  [ -n "$p" ] && basename "$p"
}

is_modem_like_iface() {
  local iface="$1" drv
  case "$iface" in
    wwan*|wwp*|usb*|rmnet*|ppp*) return 0 ;;
  esac
  drv="$(net_driver "$iface")"
  case "$drv" in
    rndis_host|cdc_ether|cdc_ncm|cdc_mbim|qmi_wwan|mhi_net|mhi_wwan_ctrl|iosm) return 0 ;;
  esac
  return 1
}

detect_wired() {
  local configured iface
  configured="$(cfg_get "$CONFIG_FILE" WIRED_WAN)"
  case "$configured" in
    ""|auto)
      # Prefer eth0 when present, but remain usable on other hardware.
      if ip link show eth0 >/dev/null 2>&1 && ! is_modem_like_iface eth0; then
        printf '%s' eth0
        return 0
      fi
      for iface in /sys/class/net/*; do
        iface="$(basename "$iface")"
        case "$iface" in eth*|en*) ;; *) continue ;; esac
        is_modem_like_iface "$iface" && continue
        [ -e "/sys/class/net/$iface/master" ] && continue
        printf '%s' "$iface"
        return 0
      done
      ;;
    none) return 1 ;;
    *)
      ip link show "$configured" >/dev/null 2>&1 && printf '%s' "$configured"
      ;;
  esac
}

discover_wired_gateway() {
  local iface="$1" route gw ipcidr guessed lease
  route="$(ip -4 route show default dev "$iface" 2>/dev/null | head -1 || true)"
  gw="$(printf '%s\n' "$route" | awk '{for(i=1;i<=NF;i++) if($i=="via"){print $(i+1);exit}}')"
  [ -n "$gw" ] && { printf '%s' "$gw"; return 0; }

  # Common dhclient / Kea / systemd-networkd lease locations; only accept a
  # gateway that belongs to the current directly-connected subnet.
  ipcidr="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk 'NR==1{print $4}')"
  [ -n "$ipcidr" ] || return 1
  for lease in /var/lib/dhcp/dhclient*.leases /run/dhclient*.lease /run/systemd/netif/leases/* /var/lib/NetworkManager/*.lease; do
    [ -r "$lease" ] || continue
    gw="$(grep -Eho '(^|[ ;])(routers|ROUTER|gateway)[ =:]+[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' "$lease" 2>/dev/null | grep -Eo '[0-9]+(\.[0-9]+){3}' | tail -1)"
    [ -n "$gw" ] || continue
    python3 - "$ipcidr" "$gw" <<'PY' >/dev/null 2>&1 && { printf '%s' "$gw"; return 0; }
import ipaddress,sys
raise SystemExit(0 if ipaddress.ip_address(sys.argv[2]) in ipaddress.ip_interface(sys.argv[1]).network else 1)
PY
  done

  # Last resort for typical LANs: try the first host, but only if reachable.
  guessed="$(python3 - "$ipcidr" <<'PY'
import ipaddress,sys
try:
    print(next(ipaddress.ip_interface(sys.argv[1]).network.hosts()))
except Exception:
    pass
PY
)"
  if [ -n "$guessed" ] && ping -I "$iface" -c 1 -W 1 "$guessed" >/dev/null 2>&1; then
    printf '%s' "$guessed"
    return 0
  fi
  return 1
}

usb_devnum_for_iface() {
  local iface="$1" p
  p="$(readlink -f "/sys/class/net/$iface/device" 2>/dev/null || true)"
  [ -n "$p" ] || return 1
  while [ "$p" != "/" ] && [ -n "$p" ]; do
    if [ -f "$p/idVendor" ] && [ -f "$p/idProduct" ] && [ -f "$p/devnum" ]; then
      if [ "$(cat "$p/idVendor" 2>/dev/null)" = "0e8d" ]; then
        case "$(cat "$p/idProduct" 2>/dev/null)" in
          7126|7127) cat "$p/devnum" 2>/dev/null; return 0 ;;
        esac
      fi
    fi
    p="$(dirname "$p")"
  done
  return 1
}

watchdog_count() {
  local iface="$1"
  journalctl -k -b --no-pager 2>/dev/null | \
    grep -Ec "rndis_host .* ${iface}: NETDEV WATCHDOG:|rndis_host .*${iface}: NETDEV WATCHDOG:" || true
}

ensure_wwan_route() {
  local iface gw method metric ip4 saved_ip prefix mtu saved_devnum current_devnum route_line
  iface="$(cfg_get "$ROUTE_CACHE" INTERFACE)"
  gw="$(cfg_get "$ROUTE_CACHE" GATEWAY)"
  method="$(cfg_get "$ROUTE_CACHE" IP_METHOD)"
  metric="$(cfg_get "$ROUTE_CACHE" WWAN_METRIC)"
  saved_ip="$(cfg_get "$ROUTE_CACHE" IP)"
  prefix="$(cfg_get "$ROUTE_CACHE" PREFIX)"
  mtu="$(cfg_get "$ROUTE_CACHE" MTU)"
  [ -n "$metric" ] || metric="$DEFAULT_WWAN_METRIC"
  [ -n "$iface" ] || return 0
  ip link show "$iface" >/dev/null 2>&1 || return 0

  case "$method" in
    ppp)
      if ! ip -4 route show default dev "$iface" 2>/dev/null | grep -q '^default '; then
        ip route add default dev "$iface" metric "$metric" 2>/dev/null && log "WWAN fallback restored: $iface metric $metric"
      fi
      ;;
    *)
      ip link set "$iface" up 2>/dev/null || true

      saved_devnum="$(cfg_get "$ROUTE_CACHE" USB_DEVNUM)"
      current_devnum="$(usb_devnum_for_iface "$iface" 2>/dev/null || true)"
      if [ -n "$saved_devnum" ] && [ -n "$current_devnum" ] && [ "$saved_devnum" != "$current_devnum" ]; then
        # A new FM350 USB instance must acquire fresh PDP/RNDIS state. Restoring
        # the previous address is harmful and produced NETDEV WATCHDOG stalls.
        ip addr flush dev "$iface" scope global 2>/dev/null || true
        ip route del default dev "$iface" 2>/dev/null || true
        return 0
      fi

      ip4="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk 'NR==1{print $4}')"

      # Restore cached runtime values only for the SAME FM350 USB instance.
      if [ -z "$ip4" ] && [ -n "$saved_ip" ] && [ -n "$prefix" ]; then
        ip addr flush dev "$iface" scope global 2>/dev/null || true
        if ip addr add "$saved_ip/$prefix" dev "$iface" 2>/dev/null; then
          [ -n "$mtu" ] && ip link set dev "$iface" mtu "$mtu" 2>/dev/null || true
          ip4="$saved_ip/$prefix"
          log "WWAN runtime IPv4 restored on $iface: $ip4"
        fi
      fi

      [ -n "$ip4" ] || return 0
      [ -n "$gw" ] || return 0
      route_line="$(ip -4 route show default dev "$iface" 2>/dev/null | grep -F "via $gw" | head -1 || true)"
      if ! printf '%s\n' "$route_line" | grep -Eq "metric[[:space:]]+${metric}([[:space:]]|$)"; then
        ip route del default via "$gw" dev "$iface" 2>/dev/null || true
        if ip route add default via "$gw" dev "$iface" metric "$metric" 2>/dev/null; then
          log "WWAN fallback restored/corrected: via $gw dev $iface metric $metric"
        fi
      fi
      ;;
  esac
}

check_wwan_liveness() {
  local iface ip4 now connected_at service_state service_pid service_name
  iface="$(cfg_get "$ROUTE_CACHE" INTERFACE)"
  [ -n "$iface" ] || { noip_count=0; return 0; }

  # If the cached interface temporarily disappears, udev recovery may already be
  # handling it. Count it the same way, but never react to a single observation.
  if ! ip link show "$iface" >/dev/null 2>&1; then
    noip_count=$((noip_count + 1))
  else
    ip4="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk 'NR==1{print $4}')"
    if [ -n "$ip4" ]; then
      noip_count=0
      return 0
    fi
    noip_count=$((noip_count + 1))
  fi

  [ "$noip_count" -lt "$NOIP_ATTEMPTS" ] && return 0

  now="$(date +%s)"

  connected_at="$(cfg_get "$ROUTE_CACHE" CONNECTED_AT)"
  if [ -n "$connected_at" ] && [[ "$connected_at" =~ ^[0-9]+$ ]] &&      [ $((now - connected_at)) -lt "$CONNECT_GRACE" ]; then
    [ $((noip_count % 10)) -eq 0 ] &&       log "WWAN $iface is inside the ${CONNECT_GRACE}s post-connect grace period; runtime repair is preferred over reconnect."
    return 0
  fi

  if [ $((now - last_recovery)) -lt "$RECOVERY_COOLDOWN" ]; then
    return 0
  fi

  # Never compete with the boot unlock, normal connection, or udev recovery.
  # In particular, modem-unlock.service can be ActiveState=activating while it
  # waits state-based for the FM350 USB/RNDIS/ttyUSB components to enumerate.
  for service_name in modem-unlock.service modem-connect.service modem-connect-recover.service; do
    service_state="$(systemctl show "$service_name" -p ActiveState --value 2>/dev/null || true)"
    service_pid="$(systemctl show "$service_name" -p MainPID --value 2>/dev/null || true)"
    if [ "$service_state" = "activating" ] || [ "$service_state" = "deactivating" ] ||        { [ -n "$service_pid" ] && [ "$service_pid" != "0" ]; }; then
      [ $((noip_count % 10)) -eq 0 ] &&         log "WWAN $iface still has no IPv4, but $service_name is active/transitioning; failover will not request a competing reconnect."
      return 0
    fi
  done

  log "WWAN $iface has had no IPv4 address for $noip_count consecutive checks; requesting one controlled modem reconnect."
  last_recovery="$now"
  noip_count=0

  # Generic path: restart the completed/idle normal modem connection service.
  # This remains modem-agnostic; the connection script selects MM/QMI/MBIM/
  # RNDIS/PPP as appropriate. --no-block avoids a circular wait.
  systemctl restart --no-block modem-connect.service >/dev/null 2>&1 || true
}

check_mm_always_connected() {
  local backend modem_id info state id binfo connected bearer_found now service_name service_state service_pid
  [ "$MM_ALWAYS_CONNECTED" = "1" ] || return 0

  backend="$(cfg_get "$ROUTE_CACHE" BACKEND)"
  [ "$backend" = mm ] || { mm_state_fail_count=0; return 0; }

  modem_id="$(cfg_get "$ROUTE_CACHE" MODEM_ID)"
  [ -n "$modem_id" ] || { mm_state_fail_count=0; return 0; }
  systemctl is-active --quiet ModemManager.service || return 0

  info="$(mmcli -m "$modem_id" -K 2>/dev/null || true)"
  state="$(printf '%s\n' "$info" | sed -n 's/^[^:]*modem\.generic\.state[[:space:]]*:[[:space:]]*//p' | head -1)"

  bearer_found=0
  while read -r id; do
    [ -n "$id" ] || continue
    binfo="$(mmcli -b "$id" -K 2>/dev/null || true)"
    connected="$(printf '%s\n' "$binfo" | sed -n 's/^[^:]*bearer\.status\.connected[[:space:]]*:[[:space:]]*//p' | head -1)"
    if [ "$connected" = yes ]; then
      bearer_found=1
      break
    fi
  done < <(printf '%s\n' "$info" | sed -n 's#^[^:]*bearers\.value\[[0-9]\+\][[:space:]]*:[[:space:]]*.*/Bearer/\([0-9]\+\).*#\1#p')

  if [ "$state" = connected ] && [ "$bearer_found" -eq 1 ]; then
    mm_state_fail_count=0
    return 0
  fi

  mm_state_fail_count=$((mm_state_fail_count + 1))
  [ "$mm_state_fail_count" -ge "$MM_STATE_FAILURES" ] || return 0

  # Do not race a genuinely running/transitioning connect, unlock or recovery
  # transaction. Type=oneshot units use RemainAfterExit=yes, so active/exited
  # with MainPID=0 is completed/idle and must NOT suppress always-connected.
  for service_name in modem-connect.service modem-unlock.service modem-connect-recover.service; do
    service_state="$(systemctl show "$service_name" -p ActiveState --value 2>/dev/null || true)"
    service_pid="$(systemctl show "$service_name" -p MainPID --value 2>/dev/null || true)"
    if [ "$service_state" = "activating" ] || [ "$service_state" = "deactivating" ] || \
       { [ -n "$service_pid" ] && [ "$service_pid" != "0" ]; }; then
      return 0
    fi
  done

  now="$(date +%s)"
  [ $((now - last_recovery)) -ge "$RECOVERY_COOLDOWN" ] || return 0

  log "Always-connected policy: modem/$modem_id state=${state:-unknown}, connected-bearer=$bearer_found; requesting generic modem reconnect."
  mm_state_fail_count=0
  last_recovery="$now"
  systemctl restart --no-block modem-connect.service >/dev/null 2>&1 || true
}

check_wwan_data_path() {
  local iface ip4 now service_name state pid baseline current
  local backend transport driver model probe_output

  iface="$(cfg_get "$ROUTE_CACHE" INTERFACE)"
  [ -n "$iface" ] || { health_fail_count=0; return 0; }
  ip link show "$iface" >/dev/null 2>&1 || return 0

  ip4="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk 'NR==1{print $4}')"
  [ -n "$ip4" ] || return 0

  now="$(date +%s)"
  [ $((now - last_health_check)) -ge "$DATA_HEALTH_INTERVAL" ] || return 0
  last_health_check="$now"

  # Never compete with unlock/connect/recovery.
  for service_name in modem-unlock.service modem-connect.service modem-connect-recover.service; do
    state="$(systemctl show "$service_name" -p ActiveState --value 2>/dev/null || true)"
    pid="$(systemctl show "$service_name" -p MainPID --value 2>/dev/null || true)"
    if [ "$state" = "activating" ] || [ "$state" = "deactivating" ] || \
       { [ -n "$pid" ] && [ "$pid" != "0" ]; }; then
      return 0
    fi
  done

  # Cellular links may drop isolated ICMP packets under load. A bearer is
  # considered alive if ANY bound probe succeeds; do not reconnect for ordinary
  # congestion or moderate packet loss.
  probe_output="$(/bin/ping -I "$iface" -c "$DATA_HEALTH_PINGS" -W 2 "$DATA_HEALTH_TARGET" 2>/dev/null || true)"
  if printf '%s\n' "$probe_output" | grep -q 'bytes from '; then
    health_fail_count=0
    return 0
  fi

  health_fail_count=$((health_fail_count + 1))
  backend="$(cfg_get "$ROUTE_CACHE" BACKEND)"
  transport="$(cfg_get "$ROUTE_CACHE" TRANSPORT)"
  driver="$(cfg_get "$ROUTE_CACHE" DRIVER)"
  model="$(cfg_get "$ROUTE_CACHE" MODEL)"

  # NETDEV WATCHDOG is specific to the observed FM350 USB/RNDIS failure mode.
  if [ "$backend" = "at-rndis" ] && [ "$transport" = "usb" ]; then
    baseline="$(cfg_get "$ROUTE_CACHE" WATCHDOG_BASELINE)"
    current="$(watchdog_count "$iface")"
    [ -n "$baseline" ] || baseline=0
    if [ "$current" -gt "$baseline" ]; then
      log "New rndis_host NETDEV WATCHDOG detected on $iface ($baseline -> $current); requesting staged FM350 USB/RNDIS recovery."
      health_fail_count="$DATA_HEALTH_FAILURES"
    fi
  fi

  [ "$health_fail_count" -ge "$DATA_HEALTH_FAILURES" ] || return 0
  [ $((now - last_recovery)) -ge "$RECOVERY_COOLDOWN" ] || return 0

  last_recovery="$now"
  health_fail_count=0

  if [ "$backend" = "at-rndis" ] && [ "$transport" = "usb" ]; then
    log "WWAN $iface has no real data path after repeated probes; starting staged FM350 USB/RNDIS recovery."
    if systemctl cat modem-connect-recover.service >/dev/null 2>&1; then
      systemctl start --no-block modem-connect-recover.service >/dev/null 2>&1 || true
    else
      log "FM350 recovery unit is unavailable; falling back to the generic modem reconnect service."
      systemctl restart --no-block modem-connect.service >/dev/null 2>&1 || true
    fi
  else
    # Generic recovery for PCIe/MHI/ModemManager, MBIM, QMI, DHCP and PPP.
    # modem-connect.sh already performs the correct bearer cleanup and reconnect
    # for the selected backend. No USB/RNDIS unbind is attempted here.
    log "WWAN $iface (${model:-unknown}, transport ${transport:-unknown}, backend ${backend:-unknown}, driver ${driver:-unknown}) has no real data path after repeated probes; requesting generic modem reconnect."
    systemctl restart --no-block modem-connect.service >/dev/null 2>&1 || true
  fi
}

reconcile_wired() {
  local iface carrier ip4 gw
  iface="$(detect_wired 2>/dev/null || true)"
  [ -n "$iface" ] || return 0
  carrier="$(cat "/sys/class/net/$iface/carrier" 2>/dev/null || true)"
  ip4="$(ip -4 -o addr show dev "$iface" scope global 2>/dev/null | awk 'NR==1{print $4}')"

  if [ "$carrier" != 1 ] || [ -z "$ip4" ]; then
    # Do not leave a stale low-metric route pointing at an unplugged WAN.
    if ip -4 route show default dev "$iface" 2>/dev/null | grep -q '^default '; then
      ip route del default dev "$iface" 2>/dev/null || true
      log "Wired WAN unavailable: removed stale default route on $iface; WWAN may take over."
    fi
    return 0
  fi

  # Cable + IPv4: wired must be primary.
  if ! ip -4 route show default dev "$iface" 2>/dev/null | grep -q '^default '; then
    gw="$(discover_wired_gateway "$iface" 2>/dev/null || true)"
    if [ -n "$gw" ]; then
      ip route add default via "$gw" dev "$iface" metric "$WIRED_METRIC" 2>/dev/null && \
        log "Wired WAN restored: via $gw dev $iface metric $WIRED_METRIC"
    fi
  else
    # Normalize only the route on the wired device; never touch WWAN.
    gw="$(ip -4 route show default dev "$iface" | awk 'NR==1{for(i=1;i<=NF;i++)if($i=="via"){print $(i+1);exit}}')"
    if [ -n "$gw" ] && ! ip -4 route show default dev "$iface" | grep -q "metric $WIRED_METRIC\\b"; then
      ip route del default dev "$iface" 2>/dev/null || true
      ip route add default via "$gw" dev "$iface" metric "$WIRED_METRIC" 2>/dev/null || true
    fi
  fi
}

last=""
while :; do
  ensure_wwan_route
  check_wwan_liveness
  check_mm_always_connected
  check_wwan_data_path
  reconcile_wired

  # Log only state changes, not every polling cycle.
  now="$(ip -4 route show default 2>/dev/null | tr '\n' ';')"
  if [ "$now" != "$last" ]; then
    log "Default routes: ${now:-none}"
    last="$now"
  fi
  sleep "$POLL_SEC"
done
FAILOVER_EOF
  chmod 0755 "$FAILOVER_SCRIPT_PATH"

  cat > "$FAILOVER_SERVICE_PATH" <<EOF
[Unit]
Description=Keep wired WAN primary and modem WAN as automatic fallback
After=vyos-router.service modem-connect.service network.target
Requires=vyos-router.service modem-connect.service
StartLimitIntervalSec=0

[Service]
Type=simple
ExecStart=$FAILOVER_SCRIPT_PATH
Restart=always
RestartSec=2
Environment=CONFIG_FILE=$CONFIG_FILE
Environment=ROUTE_CACHE=$ROUTE_CACHE
Environment=WIRED_DEFAULT_METRIC=$WIRED_DEFAULT_METRIC
Environment=WWAN_ROUTE_METRIC=$WWAN_ROUTE_METRIC
Environment=FAILOVER_POLL_SEC=$FAILOVER_POLL_SEC
Environment=WWAN_NOIP_ATTEMPTS=$WWAN_NOIP_ATTEMPTS
Environment=WWAN_RECOVERY_COOLDOWN=$WWAN_RECOVERY_COOLDOWN
Environment=WWAN_CONNECT_GRACE=$WWAN_CONNECT_GRACE
Environment=WWAN_DATA_HEALTH_INTERVAL=$WWAN_DATA_HEALTH_INTERVAL
Environment=WWAN_DATA_HEALTH_FAILURES=$WWAN_DATA_HEALTH_FAILURES
Environment=WWAN_DATA_HEALTH_TARGET=$WWAN_DATA_HEALTH_TARGET
Environment=WWAN_DATA_HEALTH_PINGS=$WWAN_DATA_HEALTH_PINGS
Environment=MM_ALWAYS_CONNECTED=$MM_ALWAYS_CONNECTED
Environment=MM_STATE_FAILURES=$MM_STATE_FAILURES

[Install]
WantedBy=multi-user.target
EOF
  chmod 0644 "$FAILOVER_SERVICE_PATH"
  systemctl daemon-reload
  systemctl enable modem-wan-failover.service >/dev/null 2>&1 || true

  # IMPORTANT: do not synchronously restart this service here. modem-connect can
  # itself be running as a systemd oneshot; waiting for another unit that used to
  # depend on modem-connect caused a circular wait/hang. Start/restart detached.
  [ "$RESTORE_ONLY" -eq 0 ] || return 0
  if systemctl is-active --quiet modem-wan-failover.service; then
    systemctl restart --no-block modem-wan-failover.service >/dev/null 2>&1 || true
  else
    systemctl start --no-block modem-wan-failover.service >/dev/null 2>&1 || true
  fi
}

