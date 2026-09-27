# Update ISO run 36339240710: installed and booted

Installed using native image_installer into a distinct name:
`999.202609250800-adf-panthor-20260927`. Source ISO and remote copy verified
against published SHA256. Previous default `999.202609250800` retained.

The previous running optional test kernel had BOOT_IMAGE ending in
`panthor-test/Image`, which upstream image.is_live_boot() misclassified because
it recognizes vmlinuz. Used a process-local normalization only after asserting
exact current BOOT_IMAGE and persistent overlay upperdir. No installed image
library modified. Native compatibility/checksum/config migration checks retained.

Full /config backup: shared boot/vyarm-before-36339240710/config.tar.
Before boot, config.boot, 1423 kiosk/state files and tailscale/state matched
byte-for-byte; SSH host keys matched. New image booted by one-shot GRUB selection
with 12-minute rollback. Regular BOOT_IMAGE ends in vmlinuz; uname6.18.50-vyos.
Panthor kernel is bundled as OPTIONAL payload, not the default kernel.

Found boot race in optional Panthor menu service: After=vyos-router.service is
insufficient because router service is Type=simple and shared /boot/grub bind
is not yet ready. Live retry succeeded after mount. Fixed source and live helper
to wait (bounded120s) for verified image bind/shared GRUB identity and version
entry, with service timeout150s. Regression reproduces delayed mount;4tests pass.
This correction is not in the downloaded ISO; requires next rebuild.

Preserved config initially selected old wayland-user-20260926 image. Explicitly
changed only container image via native CLI commit/save to
localhost/vyarm-kiosk:github-36339240710. Running Sunshine SHA256 matches
f4344497cc601a0e54b265985fab45fb21033e26a4a845d96307960aba090a40;
Chromium SHA256 matches d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6.
Weston DRM/GL and HDMI-A-1 active, two input devices associated with output.
Physical touch not newly user-confirmed on this boot.

Short physical-output Chromium fixture suite (sandbox retained,1920x1080):

| Codec | Frames | Dropped | Decoder | Result |
|---|---:|---:|---|---|
| H264 |600|7|V4L2VideoDecoder|ended|
| HEVC |300|11|V4L2VideoDecoder|ended|
| VP9 |300|6|V4L2VideoDecoder|ended|
| AV1 |300|7|V4L2VideoDecoder|ended|

All report kIsPlatformVideoDecoder=true. Not a sustained performance test.
No matched decoder timeout/IOMMU fault/panic. Normal kiosk restored.
AP hostapd@wlan0, kiosk and Tailscale services active; tailnet identity remains
100.125.185.58 and wlan0 retains10.3.141.50/24.
Sunshine remains disabled by preserved policy; no Moonlight FPS claim from this
update test. Direct GPU/RGA capture probe is not integrated in this ISO.

All rollback/browser-restore timers stopped; boot rollback unit files and
one-shot GRUB hook/environment flag removed. Current image remains running;
previous image remains default. Original old-image kexec config restored;
new-image kexec disabled for controlled GRUB boots. Raw decoder outputs retained
under shared boot/vyarm-before-36339240710/decoder-results.
