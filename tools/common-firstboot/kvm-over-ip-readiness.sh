#!/usr/bin/env bash
# Read-only runtime audit. This does not configure a USB gadget, install a
# streamer, open firewall ports or expose any device.

set -u
failed=0

check_command()
{
    if command -v "$1" >/dev/null 2>&1; then
        printf 'PASS  command: %s\n' "$1"
    else
        printf 'FAIL  command missing: %s\n' "$1"
        failed=1
    fi
}

for command in curl findmnt ip lsusb systemctl; do
    check_command "$command"
done

if findmnt -n --target /config >/dev/null 2>&1; then
    printf 'PASS  persistent configuration mount: /config\n'
else
    printf 'FAIL  persistent configuration mount missing: /config\n'
    failed=1
fi

if compgen -G '/dev/video*' >/dev/null; then
    printf 'PASS  V4L2 capture device detected\n'
else
    printf 'INFO  no V4L2 capture device currently detected\n'
fi

if [[ -d /sys/class/udc ]] && compgen -G '/sys/class/udc/*' >/dev/null; then
    printf 'PASS  USB device controller available for HID gadget use\n'
else
    printf 'WARN  no active USB device controller; capture-only mode remains possible\n'
fi

if [[ -x /config/kvm-over-ip/bin/ustreamer ]]; then
    printf 'INFO  persistent ustreamer binary is installed\n'
else
    printf 'INFO  persistent ustreamer binary is not installed (expected initially)\n'
fi

exit "$failed"
