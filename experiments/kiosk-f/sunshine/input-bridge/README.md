# Sunshine input bridge (experimental)

The Wayland kiosk has a private /dev/input and network namespace. Sunshine
uinput devices therefore need both selective character nodes and a udev add
notification inside that namespace. Receiving a Moonlight input packet alone
is not evidence of working Weston input.

`bridge.py --target kiosk --managed` follows the native remote policy, only for
Wayland + access enabled + input control. The installed service uses Sunshine
from that same container. It derives input sysfs paths through pidfd_getfd and
UI_GET_SYSNAME on Sunshine's uinput descriptors, validates virtual input paths
and the three supported keyboard/mouse names, and never selects by name alone.
No keyboard/mouse event payloads are read or logged. Existing target nodes are
never replaced. Stopping, policy disable or device disappearance removes only
nodes created by this invocation and forwards removal to Weston. Container
replacement ends the invocation; systemd restarts against the new instance.
KillMode=mixed permits cleanup subprocesses to finish on service stop.

Native Quadlet generation adds `c 13:* rw` only for Wayland remote control.
It adds no mknod capability or whole /dev/input bind mount. Changing between
control and view-only needs one native container recreation to change that
cgroup permission. Device recreation during an established control mode does
not require a compositor restart. Audio-only policy changes retain their
existing no-container-restart behavior. The rule is broad by minor number to
allow dynamic input numbers; accessibility is restricted by the created nodes.

The CLI's existing Wayland capture acceptance gate is intentionally retained.
Installing this companion alone does not declare complete Wayland remote
control release readiness. The runtime/Sunshine capture integration and portrait
acceptance still have to be completed together in a rebuilt image.

For isolated development, `--source <test-container> --target kiosk --duration
120` uses an explicitly selected source and stops within 1..600 seconds. Managed
mode refuses that override. Host root is needed; pidfd_getfd must be permitted.
The helper refuses to remove pre-existing nodes. SIGKILL/power failure cleanup
is not guaranteed; container recreation discards its private device nodes.

## Live evidence, 2026-09-27

- Running image: 999.202609250800-adf-panthor-20260927, kernel
  6.18.50-vyos-panthor-cache-test. Existing runtime github-36339240710.
- A rollback timer was armed before adding the temporary cgroup rule. Initial
  Quadlet inline comment was interpreted as an argument and caused startup
  failure; corrected immediately. Kiosk then started normally. Do not use inline
  comments on PodmanArgs.
- Only Sunshine-owned event4/5/6 were added. Weston registered Keyboard, Mouse,
  Mouse (Absolute). Local physical event0/1 remained untouched.
- H.264 direct GPU/RGA, 1920x1080, 60 FPS, absolute mouse: user confirmed visible,
  fluid pointer and correct clicks, then clarified that this was LANDSCAPE.
  Portrait input is explicitly NOT accepted by this result.
- Client: rendering 60.01 FPS, incoming 60.14 FPS, host processing mean 11.1 ms
  (8.8..140.9), network loss 0%, jitter drops 0.18%, LAN RTT 1 ms.
- Stop/restart bridge: Weston removed and re-added all three virtual devices;
  kiosk PID remained 95809. Physical touchscreen nodes remained present.
- The installed service path is prepared and unit-tested, but this live test
  used a bounded cross-container source. Same-container native-policy acceptance
  and an image rebuild are still outstanding. Do not represent this as an
  already shipped fix or completed full F acceptance.
- Revised helper completed a separate 30-second reattach/cleanup run with exit 0;
  all three virtual devices removed. Generated service uses KillMode=mixed after
  the first stop exposed systemd signalling a cleanup subprocess too.
- After tests, isolated Sunshine stopped, temporary cgroup rule removed, CSC
  reset to N, normal kiosk restarted, rollback timer cancelled. Only kiosk runs.
- 44 targeted tests passed (Sunshine, bridge, startup staging, CLI, physical-input
  generation/reconciliation). No main merge, push or image rebuild in this step.
