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
configure || builtin exit 1
native_cmd_failed=0
HEADER
  while IFS= read -r command; do
    [ -z "$command" ] || printf '%s || native_cmd_failed=1\n' "$command" >> "$script"
  done
  cat >> "$script" <<END
if [ "\$native_cmd_failed" -ne 0 ]; then native_rc=1; elif \$API sessionChanged; then commit; native_rc=\$?; if \$API sessionChanged; then native_rc=1; fi; else native_rc=0; fi
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
# Discovery and one scoped MHI recovery are already bounded inside the helper.
# Leave a persistent hardware failure visible instead of repeating resets.
Restart=no
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
  if [ "${NATIVE_FAILOVER:-0}" = 1 ]; then
    configure_native_failover "$iface" || die "Native failover setup did not complete"
  fi
  log "PASS: native VyOS WWAN $iface; APN and DHCP settings saved in config.boot. No custom connection/failover service."
  return 0
}

# Opt-in native route-health setup. No background helper or firewall hook.
remove_native_failover_setup() {
  local restore="$PERSIST_DIR/native-failover-restore.commands"
  [ -f "$restore" ] || return 0
  native_cli_transaction < "$restore" || die "Cannot restore previous native failover settings"
  rm -f "$restore"
}

configure_native_failover() {
  local mobile="$1" wired="$WIRED_WAN" active target iface kind metric commands restore
  [[ "$wired" =~ ^[A-Za-z0-9_.-]{1,15}$ ]] && [ "$wired" != "$mobile" ] || die "Native failover needs a separate wired WAN"
  active="$(/opt/vyatta/bin/vyatta-op-cmd-wrapper show configuration commands)" || return 1
  if printf '%s\n' "$active" | grep -q '^set protocols failover route 0.0.0.0/0 '; then
    die "Existing administrator failover default route: refusing to replace it"
  fi
  if printf '%s\n' "$active" | grep -Eq '^set protocols static route 0[.]0[.]0[.]0/0 (next-hop|dhcp-interface|interface|blackhole|reject)( |$)'; then
    die "Existing administrator static default route: refusing competing failover setup"
  fi
  local wired_targets="${FAILOVER_WIRED_TARGETS:-208.67.222.222 208.67.220.220}"
  local mobile_targets="${FAILOVER_MOBILE_TARGETS:-1.0.0.1 8.8.4.4}"
  python3 - "$wired_targets" "$mobile_targets" <<'CHECK_TARGETS' || return 1
import ipaddress, sys
sets = [value.split() for value in sys.argv[1:]]
assert all(sets) and not set(sets[0]).intersection(sets[1]), "Use distinct targets per WAN"
for value in sets[0] + sets[1]:
    assert ipaddress.ip_address(value).version == 4, "IPv4 targets required"
CHECK_TARGETS
  for target in $wired_targets $mobile_targets; do
    if printf '%s\n' "$active" | grep -Fq "set protocols static route $target/32 "; then
      die "Existing route to health target $target: refusing to replace it"
    fi
  done
  commands="$(mktemp "$UNLOCK_STATE_DIR/failover-XXXXXX")" || return 1
  restore="$PERSIST_DIR/native-failover-restore.commands"
  # Owned removal journal is written before commit so interrupted setup is recoverable.
  : > "$restore"; chmod 0600 "$restore"
  printf 'delete protocols failover route 0.0.0.0/0 2>/dev/null || true\n' >> "$restore"
  for kind in ethernet wwan; do
    if [ "$kind" = ethernet ]; then iface="$wired"; metric=10; else iface="$mobile"; metric=20; fi
    if ! printf '%s\n' "$active" | grep -Eq "^set interfaces $kind $iface address '?dhcp'?$"; then
      rm -f "$commands" "$restore"
      die "Native failover requires an already configured DHCP interface: $iface"
    fi
    local previous_distance
    previous_distance="$(printf '%s\n' "$active" | grep -F "set interfaces $kind $iface dhcp-options default-route-distance " || true)"
    if printf '%s\n' "$active" | grep -Fxq "set interfaces $kind $iface dhcp-options no-default-route"; then
      printf 'delete interfaces %q %q dhcp-options no-default-route\n' "$kind" "$iface" >> "$commands"
      printf 'set interfaces %q %q dhcp-options no-default-route\n' "$kind" "$iface" >> "$restore"
    fi
    # Distance 255 retains DHCP gateway discovery without installing an
    # unmonitored default route. no-default-route suppresses the router request.
    printf 'set interfaces %q %q dhcp-options default-route-distance 255\n' "$kind" "$iface" >> "$commands"
    if [ -n "$previous_distance" ]; then
      printf '%s\n' "$previous_distance" >> "$restore"
    else
      printf 'delete interfaces %q %q dhcp-options default-route-distance 2>/dev/null || true\n' "$kind" "$iface" >> "$restore"
    fi

    printf 'set protocols failover route 0.0.0.0/0 dhcp-interface %q metric %s\n' "$iface" "$metric" >> "$commands"
    printf 'set protocols failover route 0.0.0.0/0 dhcp-interface %q check type icmp\n' "$iface" >> "$commands"
    printf 'set protocols failover route 0.0.0.0/0 dhcp-interface %q check timeout 3\n' "$iface" >> "$commands"
    printf 'set protocols failover route 0.0.0.0/0 dhcp-interface %q check policy any-available\n' "$iface" >> "$commands"
    local targets="$mobile_targets"
    [ "$kind" != ethernet ] || targets="$wired_targets"
    for target in $targets; do
      printf 'set protocols static route %s/32 dhcp-interface %q\n' "$target" "$iface" >> "$commands"
      printf 'set protocols failover route 0.0.0.0/0 dhcp-interface %q check target %s\n' "$iface" "$target" >> "$commands"
      printf 'delete protocols static route %s/32 2>/dev/null || true\n' "$target" >> "$restore"
    done
  done
  if ! native_cli_transaction < "$commands"; then
    rm -f "$commands"
    warn "Native failover setup failed; restoring previous routing settings"
    remove_native_failover_setup
    return 1
  fi
  rm -f "$commands"
  log "Native failover configured: $wired preferred, $mobile backup; interface-specific health routes."
}
