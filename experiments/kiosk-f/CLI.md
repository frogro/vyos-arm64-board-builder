# Kiosk live-test CLI

Experimental branch only. The tested control surface uses the existing native
VyOS `container` configuration. `service kiosk` is still a design, not an
installed command. This avoids replacing CLI caches or changing permissions.
The example container is named `kiosk-test`; use your actual container name.

## URL and orientation

```
configure
set container name kiosk-test environment KIOSK_URL value 'https://example.org/'
set container name kiosk-test environment KIOSK_OUTPUT value 'auto'
set container name kiosk-test environment KIOSK_ROTATION value '90'
commit
save
exit
```

Rotation 0 = normal, 90 = left/counterclockwise, 180 = inverted, 270 = right.
`auto` selects the connected primary output, or the sole connected output.
With multiple connected outputs and no primary, select an output explicitly.
The existing physical mode and refresh rate are retained; logical browser
width/height are swapped by Xorg for 90/270 degrees. No Moonlight client settings
are modified. Stream aspect ratio/letterboxing and remote absolute input need
separate portrait-session testing.

Accepted URL schemes are http, https and local absolute file URLs. URL values
are passed as an argument, never evaluated by a shell. Container environment
values are free-form in upstream VyOS: kiosk validation happens on startup,
NOT during `commit`. An invalid value can therefore stop the kiosk; correct it
and commit again. Production `service kiosk` must validate before commit/apply.

## Stop and disable automatic start

```
configure
set container name kiosk-test disable
commit
save
exit
```

## Start and enable automatic start

```
configure
delete container name kiosk-test disable
commit
save
exit
```

This is native persistent enable/disable, not a separate transient pause.
The container's restart policy for crashes is separate from boot activation.

## Status and restart

```
show container
show container log kiosk-test
restart container kiosk-test
```

Administrative diagnostic command for display selection and touch mapping:

```
sudo podman exec kiosk-test cat /run/kiosk/display.json
```

Only already-exposed physical devices marked `ID_INPUT_TOUCHSCREEN=1` by udev
receive a rotation/output transformation. No USB vendor/product allowlist is
used. Relative mice and Sunshine's virtual input are not deliberately remapped.
The monitor re-enumerates every two seconds. It does not add host devices to the
container: native device mappings and hotplug permissions are a separate concern.
Existing libinput calibration is retained. Actual touchscreen/remote-input
correctness after rotation still needs hardware/user validation.

## Build and rollback

Build `container/Containerfile.cli` with `container/` as context on the ROCK,
as image `localhost/vyarm-kiosk:cli-test`. It extends the validated local
`localhost/vyarm-kiosk:mpp-test` image with xinput and the two Python helpers.
This is a local prototype, not a portable registry image. The lab still mounts
`start-kiosk` and `kiosk-session` from `/config/kiosk-test/build/`; deploy the
matching scripts when selecting the new image.

Backups: `/config/kiosk-test/start-kiosk.before-cli`,
`/config/kiosk-test/kiosk-session.before-cli`, and
`/config/kiosk-test/config.boot.before-cli`. To roll back, restore only those
two scripts, select `localhost/vyarm-kiosk:mpp-test` via native configuration,
and remove the two new environment variables. Restore the prior URL if changed.
Do not overwrite the whole router configuration from an old backup.
Pairing state and browser profile remain in the existing persistent state volume.
No extra host privilege or network listener is introduced.

## Live results (2026-09-20)

- Four local tests passed: configuration rejection, literal URL handling,
  output/geometry selection, and touch transformation math.
- Native `commit` selected `localhost/vyarm-kiosk:cli-test` successfully.
- Rotation 90 produced 1080x1920; returning to 0 restored 1920x1080.
- Chromium's process arguments contain the configured local test URL.
- `restart container kiosk-test` succeeded after fixing PID 1 signal forwarding.
  Journal: stop 02:39:15, deactivated successfully 02:39:18 CEST. The prior
  starter required SIGKILL after ten seconds and exited 137.
- Sunshine again detected h264_rkmpp after restart. A new paired client session
  after these changes has not yet been checked by the user.
- Touch mapping inventory is empty: rotated physical touch and remote absolute
  input are NOT yet validated. Existing Xorg warnings about inaccessible event4
  remain; no broad input-device access was granted to hide them.
- Final state is enabled, rotation 0, output auto, original local test URL,
  committed and saved. No router reboot was performed; persistence across a
  full reboot remains a separate test.

## Client tuning and latency observations

User accepted Moonlight H.264, 1080p/60 with forced hardware decoding, VSync off,
and 8 Mbit/s as "almost perfect" on 2026-09-20. This is a client preference,
not an image default or a universal recommended bitrate. Resolution and frame
rate were retained. User observes slight initial mouse-motion delay compared
with direct local input; its cause is not established.

Sunshine stream_audio is disabled. A roughly 19-second wlan0 capture recorded
2934 outgoing video packets and zero outgoing packets on the audio port. Video
payload averaged 1.741 Mbit/s in that sample; packet-group gaps had median
16.67 ms, 95th percentile 38.31 ms, maximum 47.77 ms. These are packet timings,
not measured frame rate or end-to-end mouse latency. No payload was retained.
Fifteen ICMP probes averaged 1.168 ms with zero loss; this short sample does not
establish absence of video packet loss. Intel video-engine counters increased
while Moonlight was running, confirming active hardware decoding. Sunshine has
an attached SysV shared-memory segment, consistent with its X11 SHM capture.
ThinkPad WLAN power saving was on; no privileged local change was made.

## Boot readiness correction

The first full reboot exposed a DHCP ordering failure: the container attempted
its explicit host-address port binds at boot +47 s, before DHCP supplied that
address at +49 s. Native restart=no left it failed, and the boot configuration
activation omitted the failed container section. The container section was
restored in isolation from the pre-change backup, with current kiosk settings.
Never save an incomplete active configuration following a failed boot/commit;
`exit` in the vbash configuration environment is not a reliable substitute for
terminating a shell script. Save only inside a successful-commit branch.

The lab now uses native `restart on-failure`, plus a **prototype systemd drop-in**
for this container only. `systemd/wait-container-addresses.py` reads explicit bind
addresses from the generated Quadlet and waits up to 60 monotonic seconds for
those addresses to exist. Wildcard listeners do not require a wait. It neither
changes interface addresses nor broadens port exposure. Retry delay is five
seconds, without a start-rate cutoff. Manual service stop remains respected.

Live installation: `/usr/local/libexec/vyos-kiosk-wait-addresses` and
`/etc/systemd/system/vyos-container-kiosk-test.service.d/kiosk-retry.conf`.
The drop-in is intentionally separate from the generated native unit; it is
NOT an upstream VyOS CLI feature. Its files must be packaged/recreated by the
future profile for image updates; this live installation alone is not update-safe.
The sample drop-in names kiosk-test; production generation must use the selected
container name. A changed DHCP lease address still requires correcting the
explicit published-address configuration; waiting cannot resolve a stale address.

The second reboot passed: native configuration retained the kiosk, the container
started at boot +49 s, and display state was 1920x1080/rotation 0. No failed
systemd units were reported; Sunshine detected h264_rkmpp. On this particular
boot the bind address was already present at the pre-start check. A separate
live test in an isolated network namespace withheld the address for two seconds:
the helper waited and returned after 2.02 seconds once it was added. The real
router interfaces were not modified. Six local unit tests passed.
Tailscale and KVM video services were also active after reboot; KVM had been
stopped manually during earlier performance isolation, so future comparisons
must account for this restored background workload. User confirmation of the
new Moonlight session and physical inputs remains outstanding.
