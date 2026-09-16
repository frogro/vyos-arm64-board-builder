# Native VyOS WWAN handover. Sourced by modem-connect.sh.
native_wwan_interface() {
  local iface
  [ "$MM_AVAILABLE" -eq 1 ] || return 1
  # Current VyOS maps wwanN to MM modem N; never configure the wrong device.
  while IFS= read -r iface; do
    [[ "$iface" =~ ^wwan[0-9]+$ ]] || continue
    [ -z "${NET_IF_REQUEST:-}" ] || [ "$NET_IF_REQUEST" = "$iface" ] || continue
    [ "${iface#wwan}" = "$MODEM" ] || continue
    printf '%s' "$iface"
    return 0
  done <<< "$NET_PORTS"
  return 1
}

native_cli_transaction() {
  local script result rc command
  mkdir -p "$UNLOCK_STATE_DIR"
  script="$(mktemp "$UNLOCK_STATE_DIR/native-cli-XXXXXX")" || return 1
  result="$script.result"
  cat > "$script" <<'HEADER'
#!/bin/vbash
source /opt/vyatta/etc/functions/script-template
configure
native_cmd_failed=0
HEADER
  while IFS= read -r command; do
    [ -z "$command" ] || printf '%s || native_cmd_failed=1\n' "$command" >> "$script"
  done
  cat >> "$script" <<END
if [ "\$native_cmd_failed" -ne 0 ]; then native_rc=1; elif \$API sessionChanged; then commit; native_rc=\$?; else native_rc=0; fi
if [ "\$native_rc" -eq 0 ]; then save; native_rc=\$?; else discard; fi
printf '%s\\n' "\$native_rc" > $(printf '%q' "$result")
builtin exit "\$native_rc"
END
  chmod 0700 "$script"
  /bin/vbash "$script"
  rc="$(cat "$result" 2>/dev/null)"
  rm -f "$script" "$result"
  [ "$rc" = 0 ]
}

write_native_service_unit() {
  # Only hardware preparation remains custom. Connection, DHCP, routing and
  # periodic redial belong to VyOS, not to the old connection watchdog.
  systemctl disable --now modem-wan-failover.service modem-connect.service modem-unlock.service >/dev/null 2>&1 || true
  rm -f "$SERVICE_PATH" "$UNLOCK_SERVICE_PATH" "$FAILOVER_SERVICE_PATH" "$FAILOVER_SCRIPT_PATH"
  cat > /etc/systemd/system/vyos-modem-hardware.service <<EOF_UNIT
[Unit]
Description=Prepare configured modem hardware for native VyOS WWAN
After=vyos-router.service systemd-udev-trigger.service
Requires=vyos-router.service
RequiresMountsFor=/config
[Service]
Type=oneshot
ExecStart=${SELF_PATH} --native-prepare
RemainAfterExit=yes
TimeoutStartSec=600
Restart=on-failure
RestartSec=30
[Install]
WantedBy=multi-user.target
EOF_UNIT
  systemctl daemon-reload
  systemctl enable vyos-modem-hardware.service >/dev/null
}

try_native_wwan() {
  local iface previous attempt ready=0 old_gateway active
  iface="$(native_wwan_interface)" || return 1
  active="$(/opt/vyatta/bin/vyatta-op-cmd-wrapper show configuration commands)"
  previous="$(printf '%s\n' "$active" | grep -E "^set interfaces wwan ${iface} " || true)"
  log "Trying native VyOS WWAN configuration for $iface."
  if [ -z "$previous" ]; then
    ip addr flush dev "$iface" scope global
    ip route flush dev "$iface"
  fi
  if {
    printf 'set interfaces wwan %q apn %q\n' "$iface" "$APN"
    printf 'set interfaces wwan %q address dhcp\n' "$iface"
    printf 'set interfaces wwan %q dhcp-options default-route-distance %q\n' "$iface" "$WWAN_ROUTE_DISTANCE"
  } | native_cli_transaction; then
    for attempt in $(seq 1 30); do
      if systemctl is-active --quiet "dhclient@$iface.service" &&
         ip -4 -o addr show dev "$iface" scope global | grep -q ' inet ' &&
         ping -I "$iface" -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
        ready=1; break
      fi
      sleep 1
    done
  fi
  if [ "$ready" -ne 1 ]; then
    warn "Native WWAN did not pass address/data-path validation; restoring its previous configuration."
    {
      printf 'delete interfaces wwan %q\n' "$iface"
      [ -z "$previous" ] || printf '%s\n' "$previous"
    } | native_cli_transaction || die "Native WWAN rollback failed; no competing connection manager will be started"
    [ -z "$previous" ] || die "Existing native WWAN configuration retained; inspect it before using a helper backend"
    return 1
  fi
  old_gateway="$(awk -F= '$1=="GATEWAY" {print $2; exit}' "$ROUTE_CACHE" 2>/dev/null)"
  {
    [ -z "$old_gateway" ] || printf 'delete protocols static route 0.0.0.0/0 next-hop %q 2>/dev/null || true\n' "$old_gateway"
    printf 'set nat source rule %q description %q\n' "$WWAN_NAT_RULE" 'AP-NET-to-WWAN'
    printf 'set nat source rule %q outbound-interface name %q\n' "$WWAN_NAT_RULE" "$iface"
    printf 'set nat source rule %q source address %q\n' "$WWAN_NAT_RULE" "$AP_NET"
    printf 'set nat source rule %q translation address masquerade\n' "$WWAN_NAT_RULE"
    if printf '%s\n' "$active" | grep -Fq 'set firewall ipv4 name VYOS-WAN-IN '; then
      printf 'set firewall ipv4 forward filter rule %q action jump\n' "$WWAN_FORWARD_RULE"
      printf 'set firewall ipv4 forward filter rule %q inbound-interface name %q\n' "$WWAN_FORWARD_RULE" "$iface"
      printf 'set firewall ipv4 forward filter rule %q jump-target VYOS-WAN-IN\n' "$WWAN_FORWARD_RULE"
    fi
  } | native_cli_transaction || die "Native WWAN connected, but routing/NAT handover failed"
  cat > "$CONFIG_FILE" <<EOF_CONFIG
MANAGEMENT=vyos
NATIVE_INTERFACE=$iface
TRANSPORT_POLICY=$TRANSPORT_MODE
MODEM_DEVICE_ID=$MODEM_DEVICE_ID
MODEM_EQUIPMENT_ID=$MODEM_EQUIPMENT_ID
UNLOCK_KIND=$MODEM_UNLOCK_KIND
EOF_CONFIG
  chmod 0600 "$CONFIG_FILE"
  rm -f "$ROUTE_CACHE" "$APN_CACHE" "$MUX_CACHE" "$BACKEND_CACHE"
  write_native_service_unit
  log "PASS: native VyOS WWAN $iface; APN and DHCP settings saved in config.boot. No custom connection/failover service."
  return 0
}
