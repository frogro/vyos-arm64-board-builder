# Preserve the successful rendering recipe

This revision restores the feature set captured in commit2d83c69
av1-main10-software.json / av1-main10-p010.json. Browser hash unchanged.
Manifest version2 separates graphics features from decoder policy and supplies
image-specific H264/AV1 buffer defaults. Both defaults enabled in THIS validated
Wayland/V4L2 recipe, not for unknown boards/images. No settings means legacy.

Switching auto/software preserves all six reference features; software adds
--disable-accelerated-video-decode. Explicit buffer overrides survive the switch.
Color correction is retained when decoder devices are unavailable, provided the
binary, Wayland environment and render device are verified. Actual per-video
hardware use remains unknown until measured. Unsupported recipes are not forced.
CLI requires image media-policy2 so old runtime helpers cannot silently apply
the previous policy. Native source staged as +media.20260922.2; no completed
native package or production installation claimed. Original evidence immutable.

Shared merge_arguments preserves unrelated enable-features instead of wiping the
entire feature list. New test runner uses the same helper as kiosk-session.
73 focused tests plus3 host regressions pass, including an exact feature-set
comparison against the saved successful reference and explicit disable override.
This restores configuration parity; it does not prove the restart cause fixed.
