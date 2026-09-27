# Corrected Actions image installed and tested on ROCK 5B

Run36314140176, workflow commit21febba, integration sourcec0e3917.

Earlier run36310823935 was falsely green: MPP ownership verification failed,
default-shell tee pipeline masked status, img.xz never produced. Never installed.
Existing destination SONAME symlinks redirected cp -a and reintroduced runner UID.
Installer now removes the destination before copying. Regression reproduces old
failure. Explicit bash pipefail and complete-artifact gate prevent partial success.
Main and regular release workflows unchanged; only ci/adf-compare-20260927 pushed.

New run logs include FULL_ARTIFACT_VERIFICATION_OK and
FULL_BUILD_AND_VERIFICATION_COMPLETE. IMG.XZ and ISO downloaded and SHA256 verified.
ISO sha256:e63adef7923e0778d5b62f6ca813bcf5cdd0e8c76bad7975b56543e7d0b927ca.
Local outputs: tmp/adf-corrected-20260927/github-36314140176/.

Installed with native image_installer add, full config backup and copied SSH keys.
One-shot trial with15min return timer and previous ADF fallback succeeded.
Running/default image999.202609250800; kernel6.18.50-vyos. Previous images retained.
Saved configuration identical except generated Release version comment. Fresh
native CLI package e4ba6e3c1403, root ownership and0644 metadata verified on target.
show system image now displays complete distinct image names. Actual op wrapper
show kiosk media kiosk and show kiosk sunshine kiosk status work. Sunshine remains
disabled per preserved user configuration. Media status correctly reports policy,
not hardware proof; separate per-video evidence below provides that proof.

Wayland DRM compositor and normal configured kiosk URL restored after probes.
ILITEK event0/event1 associated with HDMI-A-1; physical touch confirmation for this
specific boot remains pending. No failed units or matching decoder timeout/panic/
IOMMU fault. Diagnostic grep also matched informational Default domain type line;
that is not a fault.

1080p60 short fixtures, Chromium sandbox preserved, all EOS, V4L2VideoDecoder and
kIsPlatformVideoDecoder=true: H26414/600 drops, HEVC3/300, VP94/300, AV17/300.
These are5-10second smoke tests, not sustained/frame-perfect qualification or
new Profile-D capture/encoder/Moonlight end-to-end tests.

After success removed return timer/service and one-shot GRUB hook/environment
variable, set new image permanent default. No timed reboot remains.
Protected backup and raw results on ROCK:
/usr/lib/live/mount/persistence/boot/vyarm-github-36314140176/
Local raw logs/results: /mnt/entwicklung/Documents/Codex/2026-09-13/vy/work/adf-github-36310823935/
(directory retained original attempted run name; corrected run documented within).
