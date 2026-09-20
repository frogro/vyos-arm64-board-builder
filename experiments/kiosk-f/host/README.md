# Profile F host runtime fixes

Explicit staging step for the experimental F path only. Normal workflows remain
unchanged. Run against every newly assembled F rootfs before generating its
initramfs; an update image must contain these files as well as the CLI/container.
This installer is not yet connected to the normal image workflow (F itself is
still experimental).

```
python3 experiments/kiosk-f/host/install.py --rootfs "$F_ROOTFS" --cache "$CACHE" --panthor-arch10-8
```

Omit `--panthor-arch10-8` for other GPUs. The switch selects a GPU firmware
architecture, not a board name. Other Panthor architectures require their own
verified assets. Source is official linux-firmware, pinned revision and SHA256s
in install.py. Firmware redistribution licence is installed alongside the blob.
The initramfs hook requires and includes firmware and licence when selected.

The rsyslog drop-in prevents an early timezone-triggered restart from starting
rsyslog before /run/rsyslog/rsyslog.conf has been generated. It does not replace
VyOS' service, restart policy, or generated configuration. The later syslog
configuration step starts the service normally. Invalid existing configurations
still fail; this is not an error-suppression wrapper.

Live: stage with --rootfs /, daemon-reload; existing logging continues. Reprobe an
unbound GPU only after verifying the device and driver; do not unload a working
display driver. Regenerate the selected kernel's initramfs to a temporary file,
verify firmware inclusion, then replace its initramfs atomically. Keep backup.
A successful GPU probe does not prove container/browser acceleration.
