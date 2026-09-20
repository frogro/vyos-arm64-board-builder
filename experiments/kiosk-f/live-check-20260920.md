# Non-disruptive live checks, 2026-09-20 around 12:20 CEST

ROCK 192.168.178.173, container kiosk-test. No service restart or configuration
change performed during these checks.

- Container service active since 11:34:39; Result=success, NRestarts=0.
- Display status HDMI-1, rotation 90, logical 1080x1920; physical touchscreen
  mapped at /dev/input/event4. This is runtime status, not a new visual touch test.
- /config/kiosk-test/state mounted at /state; browser directory and Sunshine
  pairing-state file present. This does not establish image-update survival.
- Sunshine administration published exclusively on 127.0.0.1:47990. Connection
  from ThinkPad to ROCK LAN address port 47990 refused.
- Unauthenticated HTTPS GET requests on loopback to /, /api/config, /api/apps
  and /api/clients/list each returned HTTP 401. No credentials or state contents
  were read. curl used -k to test authorization independently of certificate trust.
- Presented certificate subject and issuer both CN=Sunshine Gamestream Host;
  validity 2026-09-19 through 2046-09-14. Client trust has not been established;
  these checks do not resolve the browser certificate warning.
- Sunshine configuration has lan_encryption_mode=2, wan_encryption_mode=2,
  upnp=disabled and stream_audio=disabled. No new streaming session or encrypted
  traffic verification was performed.
- Journal still contains Chromium DBus/UPower/GCM warnings and Xorg references
  to unexposed input nodes. Do not grant broad device access merely to hide them.
- Separate failure: modem-connect-recover.service timed out after 120 seconds
  following FM350 USB re-enumeration, ending 11:49:32 without a working data
  path. Cause and current modem connectivity need a separate investigation;
  network settings were left untouched.

Pending: built CLI package validation and interactive help/completion tests,
USB hotplug with user hardware, second connected display, image-update/rollback
test, and final certificate/access setup. Current working kiosk remains intact.

## Sunshine CLI source/companion build follow-up

Commit 98dd656 implements the separate Sunshine supervisor, native persistent
remote access/input/audio policy and operational status/pair/revoke/credential
recovery commands. 34 experiment tests passed, including actual subprocess
supervision with a dummy Sunshine and an independent desktop process. Native
VyOS config and op-mode schema/template generation passed. No claim of a new
live CLI deployment or hardware audio/stream test.

Built `localhost/vyarm-kiosk:sunshine-cli-98dd656` on ROCK without activating it:
image ID `15360200c7ca616c21b51eba17fbe4cc1e8053d810db4c6b164f0f3b78b6d6eb`.
An isolated unprivileged instance with no network, no host state mounts and all
capabilities dropped successfully imported the helper and compared the actual
Sunshine --creds output against the reset helper's reverse-byte uppercase SHA256
format using disposable test-only credentials. No real credentials were read,
printed or changed.

Docker package snapshot prepared under tmp/kiosk-sunshine-build-20260920,
version suffix `+kiosk-sunshine.f303bf1f1928`, pinned upstream 27383e4f1 and same
KVM/Tailscale recipe as installed. Initial Docker startup is awaiting the local
Ubuntu pkexec authentication dialog; no package success is implied by this note.
Kernel service vyos-f-test-kernel continues compiling. A 10-minute thread
heartbeat monitors both builds and reports actionable changes/completion only.
Monitor deliberately off and modem deliberately disconnected per user; neither
is a test failure or permission to change modem/network settings.

## Sunshine CLI live rollout, 18:07 CEST

Installed verified vyos-1x package +kiosk-sunshine.f303bf1f1928 on ROCK.
Postinst identical to previous package; dpkg --audit empty. Backup under
/config/kiosk-test/backups/sunshine-cli-20260920 includes prior package
+kiosk.72cc8e8c3d84, config.boot, session helper, Sunshine state and container
inspection, plus manual rollback notes (directory root-only).

Native interactive completion verified: show kiosk sunshine offers kiosk-test;
its commands clients/pending/status have help; remote audio offers enabled and
disabled with explanation distinguishing stream audio from local HDMI audio.

Companion migration commit failed validation because configured device input2
(/dev/input/by-id/usb-ILITEK_ILITEK-TP_V06.00.00.00-event-if00) is absent. No
container restart occurred. Candidate discarded; bind-mounted session helper
restored byte-for-byte from backup. Saved config.boot unchanged (cmp).
Current container remains localhost/vyarm-kiosk:cli-test. Asked user to reconnect
USB touchscreen before retrying. No device/network/modem/firewall edits made.
Sunshine runtime policy, access/input/audio changes and pairing API live tests
remain pending; package installation and completion are not runtime acceptance.

## Sunshine CLI runtime test, 18:13–18:15 CEST

Touchscreen reconnected as event4/event5; native migration commit succeeded after
restoring new session helper and selecting sunshine-cli-98dd656. User confirmed
local touch works again after container restart. Runtime display HDMI-1/90,
1080x1920; physical touch event4 enabled with matching rotation matrix.

Native show kiosk sunshine kiosk-test status works. Tested remote access disabled
(commit): running false; enabled (commit): running true. Tested input view-only
and audio enabled together: Sunshine config keyboard/mouse/native_pen_touch=false,
stream_audio=enabled. Restored control/audio disabled via native commit/save.
Throughout remote-only commits container StartedAt stayed 18:12:57.173924765 CEST,
Xorg host PID 734074 and Chromium host PID 734228 unchanged. No desktop restart.
Unauthenticated local HTTPS administration returns 401 after re-enable. Full
sunshine_state.json compares equal to backup without exposing its contents; all
non-CLI-owned Sunshine config lines preserved.

Limitations: no real audio source/playback test, no new pairing/revoke/password
reset (existing credentials and clients preserved), no fresh Moonlight input
test in view-only mode, no image-update test. H264 rkmpp capability found.
Status note 'Creating = selected' is too strong: startup probes also log Creating
for failing NVENC/VAAPI attempts. Correct wording before next package build;
these logs alone do not prove an active stream encoder.

USB reconnect did not restore old container touch until recreation; generic
hotplug/reconciliation remains an open issue rather than being declared solved.

## USB touch reconnect recovery

Reproduced disconnect/reconnect with identical event4/event5 numbers. Xorg still
listed the old touch registration; manual xinput disable/enable of the physical
touch device restored input, confirmed by user, without restarting desktop.
The read-only udev database exposes updated DEVPATH and USEC_INITIALIZED even
when container Xorg does not process host hotplug removal/addition.

Display watcher now compares generation and stable USB identity for already
exposed touch devices. Reopens same-device reconnect and reapplies rotation.
Missing devices skipped during enumeration; no fixed vendor/model IDs. Different
identity refused, intentionally disabled inputs not enabled, failed enable retried.
Nine display tests pass (including reconnect between polls, disconnect, identity
change, disabled device and failed enable retry).

Live companion image touch-reconnect-20260920, ID
177f8d154126092e5ae3bf3ae81f4d2d546406edfd24cc4566b3ecdcef45a21f,
contains changed display helper; host bind helper updated too, previous helper
backed up in sunshine-cli-20260920. Native image commit succeeded, portrait and
event4 reported. Post-start Xorg PID 758991, Chromium PID 759079. Awaiting user
unplug/replug test. This is limited recovery for existing node numbers; changed
event numbers/new devices still require host/container device reconciliation.

Live reconnect accepted: user confirmed automatic recovery and correct portrait touch. Log records "Kiosk touch reconnected: /dev/input/event4". Xorg PID 758991 and Chromium PID 759079 unchanged; no container/desktop restart during reconnect. Native save completed.

## HDMI audio hardware test

Live 6.18.50-vyos kernel already has SND_SOC_HDMI_CODEC=m and SND_USB_AUDIO=m.
ALSA lists rk3588-es8316, hdmi0, hdmi1. Connected monitor RTK FHD HDR advertises
two-channel LPCM in HDMI ELD; no USB sound device found. Generated low-amplitude
stereo PCM 48kHz/16bit WAV, played for four seconds with host aplay using stable
ALSA card identifier plughw:CARD=hdmi0,DEV=0. Playback exited zero and user
confirmed both tones audible from touch-monitor speaker. No mixer settings changed.

Container currently has no /dev/snd mappings. libasound and pulseaudio present,
but no running PulseAudio server (pactl connection refused). This confirms host
HDMI hardware path only, not browser audio or Moonlight audio. Next: narrowly
map selected playback/control nodes, configure user audio session and verify
Chromium playback and optional Sunshine capture independently.

## Planned handling of changed input event numbers

Use host-side stable by-id identity (by-path fallback, explicit physical-port
semantics) for authorized devices; debounce hotplug, resolve current event node
and compare against container grants/mappings. Same-node generation change uses
existing Xorg recovery. Changed node requires native container recreation with
fresh device mapping and touch rotation; do not edit saved config recursively
from a udev handler, expose all /dev/input, or grant arbitrary new devices.
Keep absent-device selection persisted; runtime handling for boot while device
is missing must be designed alongside native validation. This host reconciler
is planned, not implemented or tested. No fixed manufacturer IDs in algorithm.

## Changed-event-number experiment suspended after system trouble

Experimental host reconciler implemented; seven unit tests and four installer
tests passed. Installed service initially active. Prior-boot log shows exactly
one successful configured-device remap/container restart at Sep20 18:35:31.
Later log shows systemctl/podman timeouts from 18:41 onward. Kernel prior-boot
logs include mt7921e driver-own timeouts and repeated dwmmc interrupt latency/
CTO timeouts. User reported lost AP and performed cold boot. No conclusion
that the helper caused hardware/driver faults, and no reboot command in helper.
Prior boot continued through Sep21 01:00; new cold boot ID
67f07c55-8802-4583-8c4a-8deac8c5768a.

SSH briefly reachable on new boot. Stopped vyos-kiosk-inputs-kiosk-test.service;
confirmed inactive. Restored pre-experiment kiosk-retry.conf from
/config/kiosk-test/backups/input-reconcile-20260920, daemon-reloaded, removing
Wants dependency so future container starts do not activate watcher. Zero failed
units, but no WLAN interface in ip -brief address. Further SSH became unresponsive.
Source installer restored to accepted baseline (no automatic reconciler install).
Experimental helper/tests retained for diagnosis, NOT accepted for deployment.
Touch same-node reconnect helper remains independently active/previously tested.
Need diagnose system/AP and verify actual shifted mappings before acceptance.

## Sep21: physical connections restored; kernel test2 staged for next boot

User found WLAN card loose and LAN cable disconnected; after reseating and cold
boot reports connectivity restored. This is evidence of connection trouble, not
proof explaining every previous kernel timeout. Changed-event reconciler remains
inactive and withdrawn from auto-start; touch tests postponed by user to tomorrow.

On explicit request installed 6.18.50-vyos-f-test2 alongside 6.18.50-vyos.
Artifacts from tmp/kiosk-kernel-20260920/artifacts-v2; SHA256SUMS-v2 checked locally,
staged Image/config/DTB/modules hashes checked again on ROCK. Modules installed
in /lib/modules/6.18.50-vyos-f-test2; depmod passed, panthor vermagic and signer
checked. Created /boot/vmlinuz-f-test2 and /boot/initrd-f-test2.img (220 MiB).
Initramfs verified to contain VyOS live boot hook, live scripts and new kernel's
ext4/overlay/squashfs modules; Rockchip MMC built in. mkinitramfs fsck warning
about identifying the overlay root recorded; generated archive readable.

Normal GRUB default file unchanged (cmp against backup). Added dedicated entry
vyarm-kernel-test2 and late one-shot next_entry handler; grub-script-check passed.
Queued next_entry=vyarm-kernel-test2. No reboot performed: uname still6.18.50-vyos.
Next boot selects test2 once, clearing next_entry before boot; subsequent boot
uses original default. No watchdog automatic reboot promised if kernel hangs.
Shared root/config; this is kernel fallback, not a full filesystem rollback.
Firmware-provided DT unchanged; new DTB staged only, EFI entry has no DT override.
Backup, install status, initramfs listing and rollback instructions are under
/config/kiosk-test/kernel-test2. Cancel pending test with:
`sudo grub-editenv /run/live/persistence/boot/grub/grubenv unset next_entry`.
Boot, GPU/RGA, heaps, HDMI audio and touch on new kernel NOT yet tested.

## Sep21: test2 boot attempt unsuccessful; fallback confirmed

User authorized reboot. Before reboot uname=6.18.50-vyos and GRUB
next_entry=vyarm-kernel-test2 confirmed. After reboot LAN/SSH remained unreachable
across repeated attempts (ARP failed); no useful local-display report available.
User power-cycled on request. SSH returned after startup, uname=6.18.50-vyos,
boot ID 7e1736a9d4dc4ac29bf8700b84bda7a9, zero failed systemd units, next_entry
empty. One-shot fallback therefore worked. Journal boot list has no intervening
test2 boot recorded; /sys/fs/pstore empty. Cannot identify failure stage or assert
kernel panic from this evidence. Test2 remains installed but not selected for
next boot. Do not repeat unattended test before obtaining early boot diagnostics.

## Sep21: second test2 attempt reached userspace successfully

User requested retry; queued one-shot again and rebooted. Initial SSH polls
failed, but later SSH succeeded: uname=6.18.50-vyos-f-test2, uptime about one
minute, next_entry empty, no failed systemd units. Previous conclusion of boot
failure must not be extended to this attempt: network readiness took longer
than initial polls. User reported System Logging Service failure on display.
Journal confirms rsyslog exited status1 at monotonic49.59s then started at56.93s;
currently active. No detailed initial rsyslog error in journal, root cause open.
Existing override uses /run/rsyslog/rsyslog.conf and automatic restart. No logging
configuration changed. /dev/dma_heap/system exists. /dev/dri lists card0 only,
no render node observed; GPU/video capability still requires investigation.
Boot success is not functional acceptance of RGA/audio/touch/decoding.

## Sep21: rsyslog startup condition and Panthor firmware corrected live

Cause traced in installed system_timezone.py: unconditional `systemctl restart
rsyslog` occurs before system_syslog.py renders /run/rsyslog/rsyslog.conf.
Added independent 50-vyarm-config-ready.conf ConditionPathExists drop-in without
replacing existing override or generated logging config. Config validation -N1
passes, service stays active. Transient systemd tests confirm missing config
skips start successfully, present config permits it. Boot confirmation pending.

Installed official linux-firmware arch10.8 blob and redistribution licence,
revision and SHA256s pinned in host/install.py. Rebound previously unbound
fb000000.gpu to panthor: successful firmware load, CSF interface1.5.0,
Initialized panthor1.5.0; card1 and renderD128 appear. Cooling-device warning
remains, not investigated here. This validates driver initialization, not browser
rendering or video decoding. No modem changes. Backup original rsyslog drop-ins
and test2 initramfs: /config/kiosk-test/backups/host-fixes-20260921.
Initramfs regenerated successfully to temporary path, firmware inclusion verified
with lsinitramfs, then atomically replaced /boot/initrd-f-test2.img. No reboot.
Three host-installer tests pass (other GPU/no firmware fetch, checksum rejection,
staging-root escape rejection); staging twice also checked. Both live corrections
are reproducibly staged by committed installer; F build checklist updated.

## Sep21: missing MPP traced to boot DT selection, not missing driver

Read-only diagnosis: mpp_service platform driver registered, but live FDT has no
mpp-srv or rkvenc-core nodes. Installed /boot/dtb/rockchip/rk3588-rock-5b.dtb and
artifacts-v2 DTB both contain enabled rockchip,mpp-service and RKVENC nodes.
Earlier boot journal (-3 at diagnosis) confirms MPP service and both encoder cores
probed successfully. Current and preceding old-kernel boots lacked those probes.

/usr/share/vyos/templates/grub/grub_vyos_version.j2 is owned by vyos-1x and lacks
the builder-added devicetree line. Generated current version entry lacks it too;
older version entries retain it. Strong inference: experimental CLI package
upgrade replaced image-stage template patch; regeneration then lost DT selection.
Kernel test entry copied this defective entry. Earlier reasoning that absence of
a devicetree.mod meant no GRUB support was incorrect: fdt.mod exists and prior
entries use devicetree. Existing tools/patch-vyos-grub-board-dtb.py implements
image-stage correction, but live package deployment must also preserve/reapply it.

No boot configuration changed in this analysis. Next repair: preserve template
across package updates, explicitly select matching test2 DTB in isolated entry,
verify boot syntax and queue a controlled test. Do not invent live MPP device
nodes or change device grants to bypass missing hardware initialization.
