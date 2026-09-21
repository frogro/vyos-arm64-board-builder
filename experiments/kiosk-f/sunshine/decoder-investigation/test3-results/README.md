# Live stateless decoder comparison — 2026-09-21

PASS on ROCK5B, kernel 6.18.50-vyos-f-test3, initramfs v2 including firmware.
Device: /dev/video2 rkvdec, /dev/media0; platform fdc38100.video-codec.
Second core is ignored by the driver (no multicore support); no multicore claim.

Ran test-stateless-decode.sh with isolated image
`localhost/vyarm-kiosk:gst128-decoder-test-20260921` and prepared synthetic
1280x720, 30fps, 90-frame H.264/HEVC fixtures including B-frames. Explicit
v4l2slh264dec/v4l2slh265dec: no automatic software decoder selection. Outputs
converted to I420 and compared byte-for-byte with software-decoded references.
Each codec passed three independent process starts (six matching outputs).
Service result success, exit0. Logs and output SHA256 attached. No new decoder
or IOMMU fault reported. Existing kiosk F and KVM D services active afterwards.

This proves these fixtures through the V4L2/GStreamer hardware path. It does not
prove Chromium integration, every codec profile, 4K performance, physical touch,
Moonlight picture quality, or release-image readiness.

Boot fallback was exercised: unconfirmed test3 boots were timed back to original
VyOS kernel. Initial missing WLAN firmware in the test initramfs was corrected;
v2 contains host firmware generically. Successful SSH-confirmed boot canceled
the timer; persistent boot fallback timer subsequently disabled. Normal GRUB
default unchanged, next_entry empty. A normal reboot returns the original kernel.
Early pre-userspace hangs still require manual power cycling.

Initramfs v2 SHA256:
5d3a275cb0afacb08cc09c819e3cddca20c2e34276254eddeb6f466ff819b799
