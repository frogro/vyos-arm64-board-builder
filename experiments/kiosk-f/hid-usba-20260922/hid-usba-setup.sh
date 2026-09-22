set -eu
g=/sys/kernel/config/usb_gadget/vyos-kvm
t=/sys/kernel/config/usb_gadget/vyarm-hid-probe
test -z "$(cat "$g/UDC")"
test ! -e "$t"
systemd-run --unit=vyarm-usba-safe-restore --on-active=90 /bin/sh /run/vyarm-usba-probe-cleanup.sh
mkdir "$t"
echo 0x1d6b > "$t/idVendor"
echo 0x0104 > "$t/idProduct"
echo high-speed > "$t/max_speed"
mkdir "$t/strings/0x409"
echo VyARM > "$t/strings/0x409/manufacturer"
echo 'Isolated HID test' > "$t/strings/0x409/product"
echo VYARM-HID-PROBE > "$t/strings/0x409/serialnumber"
mkdir "$t/functions/hid.keyboard" "$t/configs/c.1"
for a in protocol subclass report_length report_desc; do cat "$g/functions/hid.keyboard/$a" > "$t/functions/hid.keyboard/$a"; done
echo 1 > "$t/functions/hid.keyboard/no_out_endpoint"
ln -s "$t/functions/hid.keyboard" "$t/configs/c.1/keyboard"
echo fc000000.usb > "$t/UDC"
