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
