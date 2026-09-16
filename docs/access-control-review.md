# KVM and Tailscale access control review

Reviewed: 2026-09-16. Scope: repository integration and read-only checks on the
ROCK 5B running 999.202609151917, MediaMTX v1.20.0. This is not a completed
operator isolation or firewall acceptance test.

## Agreed policy

Use native VyOS configuration ownership, commit/save, firewall groups and input
filtering. Use Tailscale tailnet policy for access over Tailscale. Do not add a
parallel web identity/role system or integrate VyManager accounts. The deploying
administrator owns the permitted devices/networks/users. IP filtering identifies
network endpoints, not people. Viewer-only versus remote-control roles are not
provided by these network rules.

## Checked integration

- `service kvm-over-ip` and `service tailscale` declare native configuration
  owners. The profile source preparation adds definitions and scripts before
  upstream VyOS package generation; it does not replace the login permission
  model.
- The reviewed profile tooling does not introduce its own sudoers policy.
- Operational definitions include `show tailscale`, `show kvm-over-ip`, and
  `request tailscale login`. Login changes authentication state: it must not be
  treated as a read-only status command when granting operator commands.
- On the live device, Tailscale state and runtime JSON are mode 0600. The state
  directory is 2700. KVM MediaMTX configuration and HID device are mode 0600.
  Executable helpers checked are root-owned mode 0755, without setuid bits.
- File permissions and native configuration owners alone do not establish
  correct operator isolation. Positive and negative operator execution tests,
  including direct helper access and admin-to-operator demotion, remain open.

## Listener inventory and firewall implications

The following are observed listeners, not a list of ports to open indiscriminately.
Binding to an address is not a client allowlist. Restrict traffic destined to the
router itself (input), and cover IPv4 and IPv6. Forward rules are separately
required for routed subnets.

| Component | Observed/default endpoint | Deployment policy |
| --- | --- | --- |
| KVM WebRTC page/signaling | TCP 8889 on all IPv4 addresses | Permit only approved sources; CLI port is configurable |
| WebRTC media | UDP 8189 wildcard listener | Apply the same source restrictions; not controlled by the HTTP listen-address |
| Internal RTSP publishing | TCP 8554 on 127.0.0.1 | Keep local; no LAN opening needed |
| Additional MediaMTX MoQ endpoints | TCP/UDP 8892, UDP 8893 wildcard listeners | Unneeded for current WebRTC flow; block externally or explicitly disable in generated configuration after validation |
| MediaMTX other UDP sockets | 5353 and ephemeral IPv4/IPv6 ports observed | Do not broadly allow ephemeral ports; identify required ICE/discovery behavior during acceptance tests |
| uStreamer, alternative backend | CLI-selected HTTP TCP port (default 8889), `/stream` | Derived from runner, not switched/tested in this review; apply equivalent restrictions |
| SSH | TCP 22 on IPv4/IPv6 | Independent management access policy and account authentication |
| Tailscale transport | Dynamic UDP and tailnet TCP listeners observed | Transport ports are distinct from application permissions; do not hardcode this snapshot as a permanent policy |

The MediaMTX generator disables RTMP/HLS/SRT/API/metrics/playback, but omits
`moq`. Version 1.20.0 enables MoQ by default. The extra listeners were confirmed
on the live device. A policy that protects only TCP 8889 is therefore incomplete.
This review did not change service configuration or interrupt the stream.

No viewer authentication is configured in the generated MediaMTX settings.
CORS (`webrtcAllowOrigins`) is not access control. Also review MediaMTX's default
publish permissions before claiming that allowed clients have read-only access.

## Tailscale and native firewall coexistence

Tailscale policy controls tailnet traffic, not direct LAN access. Tailnet
membership alone is not a least-privilege policy: inspect actual grants/ACLs.
The configured default netfilter mode is `on`; Tailscale installs its own rules.
Validate effective rule traversal and counters alongside VyOS input/forward
rules rather than assuming a rule shown in config.boot wins in every path.
Do not set netfilter mode off without supplying and validating replacement
forwarding/NAT rules. No new firewall engine is required.

## Acceptance work still required

1. Agree the deployment allowlist before applying restrictive live rules.
2. From allowed and denied clients, test direct stream URLs and every enabled
   backend/protocol, including IPv6 and direct LAN bypass of Tailscale.
3. Check effective VyOS/Tailscale rules and counters, including subnet routing.
4. Test a narrowly scoped native operator: allowed status commands work;
   configure/commit, Tailscale login unless explicitly granted, state files,
   HID writes and direct privileged helpers remain inaccessible.
5. Confirm role revocation/demotion removes old privileges; test update/reboot
   persistence and repeat the listener inventory after dependency upgrades.

These are validation and deployment tasks. Any discovered permission bypass
would require correcting our integration, not inventing a parallel role system.

## References

- https://docs.vyos.io/en/rolling/configuration/firewall/groups.html
- https://blog.vyos.io/vyos-project-august-2025-update
- https://tailscale.com/docs/features/access-control/acls
- https://raw.githubusercontent.com/bluenviron/mediamtx/v1.20.0/mediamtx.yml

## Bounded live operator check (2026-09-16)

A temporary native operator account/group allowed only `show tailscale` and
`show kvm-over-ip`. Interactive SSH login succeeded. `configure` was unavailable;
`show configuration commands` was explicitly denied by the command policy.
An arbitrary `sudo -n /usr/bin/true` did not execute.

Under the operator UID, read-access checks denied config.boot, Tailscale state
and runtime JSON, and KVM MediaMTX/input configuration. Write-access checks denied
/dev/hidg0, /dev/hidg1 and /dev/hidg2; no HID bytes were sent.

**Unresolved functional failure:** both explicitly allowed status commands failed
with `Failed to execute Unix call setuid: Operation not permitted`. This does
not demonstrate an admin privilege bypass, but operator status delegation has
not passed. Determine whether the native command runner/image packaging or our
command integration causes this before claiming operator support. Do not fix
by broadly granting sudo or adding an unreviewed setuid bit.

Noninteractive SSH shorthand and runuser-based command-runner dry runs were
inconclusive due to shell/environment identity differences; they are not counted
as successful policy tests. Tailscale login, direct helper bypasses, demotion,
and exhaustive isolation remain untested.

The temporary account and operator group were removed through native commit;
operators.json returned to its original contents and passwd no longer contained
the account. No save was performed. Working/active configuration comparison was
clean. Tailscale, KVM input, MediaMTX and video services remained running at the
final check. No build was started and no production permission policy changed.

## Cause identified in follow-up (2026-09-16)

The installed `/usr/bin/vyos-op-run` is root:root mode 0755, owned by
`vyos-1x` version `999.0-14905-g28207a306+kvm-tailscale.250ee99b8fd4`.
The old `vyos-utils` package is not installed. The native runner checks command
permissions and then calls `Unix.setuid 0` before invoking the command. Without
the intended setuid installation this fails for the operator, explaining both
status-command failures before either extension runs.

The former upstream vyos-utils postinst explicitly sets `chmod u+s
/usr/bin/vyos-op-run`. The merged vyos-1x packaging copies the executable but
the inspected upstream and installed vyos-1x postinst contain no corresponding
step. Local source-review src/ocaml/vyos_op_run.ml lines 507-508 confirms the
permission-check/setuid sequence. Our profile preparation preserves those
upstream packaging targets. The live root mount has no nosuid option.

This identifies a native runner packaging problem, not a need for a second
role system or a general sudo grant. No live permissions were modified in this
follow-up. Restoring upstream-intended runner installation and repeating both
allowed and denied command tests is still required before marking this fixed.

Source references:
- https://github.com/vyos/vyos-utils/blob/current/debian/vyos-utils.postinst
- https://github.com/vyos/vyos-utils/blob/current/src/vyos_op_run.ml
- https://github.com/vyos/vyos-1x/blob/current/debian/vyos-1x.postinst
- https://github.com/vyos/vyos-1x/blob/current/debian/rules

## Fix and live retest (2026-09-16)

Profile package preparation now restores the former upstream postinst command
`chmod u+s /usr/bin/vyos-op-run || exit 1`, guarded by the known native
permission-check/setuid source sequence. Existing upstream restoration is not
duplicated. Binary package validation checks that the runner and installation
step are included. This applies to rebuilt native KVM/Tailscale profile packages;
unmodified base-only builds are not changed by this profile preparation.

On the ROCK, mode 0755 reproduced the same failure for upstream `show version`.
After restoring root:root mode 4755, an interactive SSH operator could execute
all three explicitly allowed commands: `show version`, `show tailscale`,
`show kvm-over-ip`. `configure` and `request tailscale login` were unavailable;
`show configuration commands` was explicitly denied. Direct file-read checks
still denied config.boot, Tailscale state and MediaMTX config. Arbitrary sudo
still failed. No broad sudo grant or parallel permission system was introduced.

The live runner correction is retained. Eight profile preparation tests pass,
as do shell syntax validation of the patched real upstream postinst, Python
syntax checks and git diff whitespace checks. A full binary/image build has
not been run yet. This bounded check does not replace the remaining firewall,
role-demotion and exhaustive operator-isolation acceptance work.
