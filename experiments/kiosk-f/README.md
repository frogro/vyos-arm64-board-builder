# Profile F: live kiosk experiment

Development baseline: e24a9f1 from main-test (the tested builder line), not the older main branch. Branch: feature/kiosk-profile-f. E remains a separate design only. No workflow or production profile selection is changed.

## Verified on ROCK 5B

- Debian trixie container, native VyOS container configuration, Xorg modesetting software rendering, Chromium kiosk.
- Local HDMI display, Logitech keyboard/mouse and ILITEK touch confirmed by user.
- Xorg requires -keeptty to retain the VT controlling terminal. SYS_ADMIN is still present and needs review.
- Sunshine 2026.914.233613 (63d35f702ee9e362e43263742981836ec0710384), X11 capture and libx264 software encode; Moonlight stream confirmed by user.
- ThinkPad Intel VA-API decode verified by increasing GPU video-engine counters.
- Browser state and Sunshine identity reside in /config/kiosk-test/state. No credentials or pairing material are stored here.
- Browser profile lock cleanup is guarded by flock; stable container hostname kiosk-test.
- Chromium TranslateEnabled=false policy is installed live. Browser process is supervised in kiosk-session.
- Openbox show-desktop keybinding removed in persistent live configuration. Seed/recovery of that configuration remains to be packaged.

## Hardware encoding probe: 2026-09-20

capture-x11-probe.py captured 60 actual 1920x1080 desktop frames using XGetImage in the running container. The host ffmpeg-rockchip converted BGR0 to NV12 and encoded H.264 with h264_rkmpp. No VyOS image rebuild, no kernel change. Exit status 0; 60 frames completed in 5.26 seconds (~11 fps), 155 KiB encoded. Software Sunshine was running concurrently.

This proves access to MPP, NOT fast screen capture or Sunshine MPP integration. MPP emitted invalid-memory-pool warnings at shutdown; investigate before using this path in production. The probe is intentionally not a streaming service.

The installed Sunshine source has no rkmpp encoder backend. Its FFmpeg is not replaced by installing an ffmpeg executable. A tested source change and compatible FFmpeg/MPP build are needed; hardware acceleration was not enabled at that initial probe. The subsequent
patched implementation is now running: see `sunshine/README.md` for the verified
MPP encoder, encrypted Moonlight session, limitations and rollback. The examined rockchip-vaapi project is decode-only and does not solve encoding.

## Existing native CLI (live test name)

Run as a VyOS configuration administrator:

```text
configure
set container name kiosk-test environment KIOSK_URL value 'https://example.com/'
commit
save
exit
```

Enable/disable uses native `set container name kiosk-test disable` / `delete container name kiosk-test disable`, followed by commit/save. Operational restart: `restart container kiosk-test`.

These are real existing commands. There is no `set service kiosk` implementation yet. Do not modify generated systemd units; the native container owner regenerates them.

## USB limits

The disconnected touchscreen is deliberately not a required device for the current keyboard/mouse test. Keyboard, pointer and system-control source paths use /dev/input/by-id where available. One consumer-control event source still uses its event number. Destination event numbers and Xorg udev discovery require more work for arbitrary enumeration. Missing required USB devices can still reject a commit/start; unplug/replug automation is not implemented. Do not call this generic hotplug support.

## Security and remaining work

- Keep Chromium sandboxed; review SYS_ADMIN and DRM/VT permissions.
- Web administration bound to host 127.0.0.1:47990, accessed via SSH tunnel. Stream ports bound to test LAN address; UPnP disabled. Certificates and mandatory stream encryption still require review.
- uinput absent in running kernel. Verify X11 fallback input path before asserting a mandatory kernel rebuild.
- GPU rendering modules absent. Browser GPU acceleration is separate from MPP video encoding.
- Package default Openbox/Sunshine configs reproducibly; existing configure-kiosk.vbash is an INITIAL LAB SNAPSHOT ONLY, not a production installer (it contains fixed lab interfaces; USB bindings must be generated from discovery).
- Dedicated kiosk CLI/schema, native API compatibility, dynamic USB handling, image update integration, browser crash test, reboot test and security tests remain open.
- Parallel vyos-kvm-video service is temporarily stopped for measurements; configuration remains present. Restore with `sudo systemctl start vyos-kvm-video.service` when returning to KVM tests.

No reboot or builder release was started for this experiment. Rollback: restore the saved pre-kiosk configuration on the ROCK and select the existing image; branch deletion is not required to continue normal builds.

## Generic input requirement

`discover-inputs.py` enumerates udev USB input classes, not manufacturers or model IDs. It prefers by-id, falls back to by-path, and reports unstable event-only paths explicitly. Default selection is keyboard/mouse; touch is opt-in. Read-only live discovery on the ROCK found the connected keyboard and mouse without a hardware-specific rule. Other hardware and hotplug reconciliation are not yet tested. Persist selection policy, not the current Logitech/ILITEK identifiers. For multiple devices allow explicit administrator selection. Device ACL reconciliation and restart behavior remain required before claiming automatic hotplug support.
