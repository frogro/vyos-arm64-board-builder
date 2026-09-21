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
