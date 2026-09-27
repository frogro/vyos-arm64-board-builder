# Optional Panthor cached-mapping test kernel

This is a separate ROCK 5B test payload, not a replacement for the normal kernel.
The A–D+F comparison workflow builds it natively on an ARM64 runner, using the
hash-pinned corrected 6.18.50 source and configuration from the previous A–D+F
build. The cached-maps preparation tool verifies every affected baseline file
before applying the audited backport. Kernel release:
`6.18.50-vyos-panthor-cache-test`.

All modules, including the standard VyOS out-of-tree modules, are rebuilt and
signed with this build's new key. Only the kernel, public configuration, DTB,
System.map and installed modules leave the runner. No private signing key is
uploaded. The normal decoder kernel and its module tree remain unchanged.

`KIOSK_F_TEST_KERNEL` explicitly opts an F image assembly into staging these
artifacts. It has no effect on ordinary builds when absent. A separate matching
initramfs and all modules are packaged in the root filesystem, so both the SD
image and update ISO carry the test payload. On first boot, the oneshot helper
copies it into that installed image's own `/boot/<version>/panthor-test/`
directory and adds an optional GRUB entry. It preserves the standard entry,
root-image selection, boot options and saved default. A changed/unrecognized
GRUB template fails closed. No automatic test-kernel reboot is performed.

The normal boot must complete once before this optional menu entry is available.
Do not select it remotely without a separately verified recovery path. Selecting
the normal image again uses the unchanged normal kernel. Panthor userspace must
request the new cached mapping mode to benefit; a kernel build alone does not
prove improved OpenGL/KMS readback or solve Sunshine latency. The new Sunshine
binary includes opt-in timing instrumentation for that comparison; instrumentation
and experimental RGA are not enabled by default. Existing CLI restrictions on
Wayland remote access are retained pending performance acceptance.

Validation before dispatch: boot-menu isolation tests, 95 F regression tests,
and 31 existing host/CLI/ownership/GRUB tests pass. The workflow also verifies
normal kernel/DTB bytes, identical SD/ISO root filesystems, test payload and
initramfs contents, CLI ownership, Chromium checksum and Sunshine dependencies.
A full build and live boot remain separate pending checks.

## First CI run correction

Run 36333055879 completed the kernel and in-tree modules, then failed configuring
ipt-netflow because the new runner lacked libxtables-dev. The established main
workflow already installs libxtables-dev, iptables and pkg-config. The test
workflow now includes those packages and checks the xtables header with the C
compiler before downloading or building the kernel. This was a runner dependency
omission, not a Panthor compiler failure; it provides no live stability evidence.

## Live boot path correction

The live system binds /run/live/persistence/boot/<version> directly onto /boot,
with the global GRUB directory bind-mounted below it. The menu helper now verifies
that mapping by inode identity and stages under /boot/panthor-test. GRUB still
uses partition-relative /boot/<version>/panthor-test paths. Tests cover the live
bind layout, whole-boot layout and mismatched mounts. The existing default is not
changed. A workflow dispatch can reuse the verified kernel artifact while building
an image with this helper fix, avoiding an unnecessary kernel rebuild.

## Live-test boot argument trap (2026-09-27)

Do not append an independent `panic=30` to the optional menu. VyOS
`system_option.py` manages this argument; if it differs from the saved config,
boot-time configuration applies `kexec -l /boot/vmlinuz` and reboots into the
normal kernel. This was reproduced twice: the optional kernel and Panthor
initialized, then `system_option` initiated kexec. The inherited BOOT_IMAGE text
still named the test Image afterward, so it is not proof of the running kernel.
Always verify `uname -r` and the kernel journal. Preserve the installed menu's
arguments exactly and use the independent return timer / watchdog for recovery.

## Live Sunshine result (2026-09-27)

After preserving the normal boot arguments, `uname -r` confirms the optional
kernel. Wayland/Weston uses Mali-G610 (Panfrost), Mesa 25.0.7, with physical HDMI
at rotation90. A separate bounded container used the existing
`audio-hevc-test3-20260927` Sunshine runtime, KMS capture and hevc_rkmpp, RGA off.
Moonlight requested 1920x1080/30fps, 2000kbps, hardware client decoding,
vsync/frame pacing off. A 40-second process window yielded:

- Received/rendered: 14.33fps.
- Host processing min/max/mean: 260.7/404.2/290.8ms.
- Network latency: 1ms; network/jitter drops: 0%/0%.
- Client decode: 1.93ms average.

Historical Wayland/KMS control:13.70fps,280.6ms mean host time; privileged
capture control:12.75fps,284.8ms. This short historical comparison is not a
same-session A/B (network and scene differ). It shows no material improvement
from the kernel alone with unchanged Mesa/OpenGL userspace. It is not a Vulkan,
new Mesa or instrumented Sunshine result. No GPU hang appeared during the test.
The test container and return timers were removed/stopped afterward; normal
kiosk stayed running. Optional kernel remains active until the next reboot;
normal GRUB default remains unchanged. No production CLI/credentials changed.
