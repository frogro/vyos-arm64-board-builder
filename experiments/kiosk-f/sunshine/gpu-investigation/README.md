# Isolated GPU rendering verification, 2026-09-21

On test2 kernel with matching DTB and installed Mali CSF firmware, ran the current
kiosk image in a separate disposable container, network disabled, granting only
/dev/dri/renderD128 and mounting egl-probe.py read-only. EGL surfaceless context,
GLES red clear and readback succeeded:

```
{"renderer":"Mali-G610 (Panfrost)","version":"OpenGL ES 3.1 Mesa 25.0.7-2+deb13u1","pixel":[255,0,0,255],"egl":[1,5]}
```

First attempt needed libGLESv2 dispatch library absent in image; final probe uses
standard eglGetProcAddress for GLES functions. No packages installed in live
kiosk. This establishes hardware-rendered EGL/GLES with the current Mesa image,
not Chromium acceleration, video decode, zero-copy capture or GPU performance.
The live kiosk still maps only card0 and Xorg AccelMethod none. Next integration
must scope render-node grants/group access and validate Xorg/Chromium separately.

Repeated successfully as unprivileged container user `kiosk`, granting the
host render node's numeric group as a supplementary group (`--group-add`).
Same Mali-G610 renderer and red pixel result. This establishes a scoped
non-root device permission path, but does not yet validate Chromium/Xorg.

## Initial Chromium headless probe (2026-09-21 overnight)

A disposable network-disabled container as user kiosk with render node/group,
Chromium headless, `--enable-gpu --use-gl=angle --use-angle=gles` could not create
WebGL2. ANGLE explicitly failed opening the default X display. This tests an
incomplete display setup, not a broken Mali driver. Next test must provide an
authorized X socket/Xauthority or establish a supported surfaceless Chromium
backend. The plain EGL probe above is already surfaceless and passes.
`webgl-probe.html` reports actual renderer and a red pixel, allowing software
fallback to be detected rather than treating a rendered page as acceleration.
The disposable probe used --no-sandbox only in its network-disabled container;
this must not become a production kiosk policy.

## Chromium with authenticated X11 access

`chromium-probe.sh` shares the live container's network/IPC namespace for the
abstract X socket and copies its Xauthority into a temporary read-only mount.
It grants the sole discovered render node and its numeric group, runs as kiosk,
and uses a temporary browser profile. The live browser/config is not changed.
Result on the HEVC candidate: `ANGLE (Mesa, llvmpipe (LLVM 19.1.7 128 bits),
OpenGL ES 3.2)`, red pixel correct. Script correctly returns failure for software
renderers. Current Xorg explicitly uses AccelMethod none. Thus render-node access
alone is insufficient for this X11/ANGLE path. A controlled glamor/Xorg test with
independent rollback is still required; no production flag was changed.

## Controlled live glamor test: SUCCESS (2026-09-21 01:18 UTC)

Saved the runtime Quadlet, image ID, Xorg configuration and Sunshine state under
/config/kiosk-test/builds/glamor-20260921 on the ROCK. Installed an independent
systemd rollback timer (180 seconds) before changing anything. Temporarily added
the render node and mounted an Xorg config changing only AccelMethod none to
glamor; restarted the kiosk. Image, saved VyOS configuration and browser flags
were unchanged.

Xorg: `glamor X acceleration enabled on Mali-G610 (Panfrost)`.
Disposable Chromium probe: `ANGLE (Mesa, Mali-G610 (Panfrost), OpenGL ES 3.1)`,
red pixel [255,0,0,255], exit 0. This confirms the X11/ANGLE rendering path with
its explicit probe flags, not hardware video decoding or production browser
performance. Production Chromium without probe flags remains to be checked.

Saved Xorg log and probe log in the test directory, explicitly executed rollback,
then cancelled the timer. Verified restored kiosk service active, Chromium running,
1080x1920 portrait output, both ILITEK input devices enumerated, no failed systemd
units. Physical touch accuracy and perceived output quality were not tested.

Next: opt-in generic acceleration setting with scoped render-node selection,
permissions and software fallback, plus production-browser diagnostics. Do not
hardcode ROCK5B/card numbering into normal provisioning based on this one test.

## Opt-in integration prepared (not deployed)

Container startup supports KIOSK_GRAPHICS=software (unchanged default) or auto.
Auto requests glamor only if character render nodes have already been explicitly
granted to the container. No device access, board matching or fixed render number
is added by this option. The display card selection remains the existing Xorg
configuration; multi-GPU selection is not solved by this helper.
Runtime configuration is generated under /run/kiosk, leaving templates/settings
intact. If accelerated Xorg fails startup or lacks a hardware glamor log result,
startup retries once with the original software template. Mode is recorded in
/run/kiosk/graphics-mode; failed accelerated log is preserved under /state.
Base and CLI-layer Containerfiles copy the helper/startup changes. Existing live
images/bind mounts have NOT been changed. Five new selection/validation tests
and all 55 kiosk tests pass. Live startup/fallback validation is the next step;
this commit does not claim that the new fallback was exercised on hardware.

## New startup and failure recovery live validation (2026-09-21 01:44 UTC)

Tested d317d80 startup/helper via temporary read-only mounts and runtime-only
KIOSK_GRAPHICS=auto plus the explicitly granted render node. Before changing the
runtime Quadlet, saved it and Sunshine state in graphics-startup-20260921 and
scheduled an independent 300-second rollback. Startup selected glamor; Chromium
probe again returned Mali-G610 and correct red pixel.

Then deliberately injected a nonexistent Xorg driver into ONLY the generated
accelerated test configuration. Xorg reported no drivers/no screens. Startup
preserved the failure log, retried the unchanged software template, reported
`software`, and recovered the portrait 1080x1920 display. The injection was in a
remote diagnostic copy, never in committed production code.

Explicitly rolled back the original Quadlet and cancelled the timer. Original
service active, both ILITEK devices enumerated, no failed units; Quadlet matches
its saved copy. New startup is live-validated but not permanently deployed.
Physical touch and actual Moonlight HEVC quality remain manual checks.
