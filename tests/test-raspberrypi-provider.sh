#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

for cmd in dtc fdtoverlay fdtget dpkg-deb sha256sum; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: provider test requires $cmd" >&2
        exit 1
    }
done

mkdir -p \
    "$WORK/firmware/overlays" \
    "$WORK/version" \
    "$WORK/artifacts/dtb/broadcom"

cat > "$WORK/firmware/config.txt" <<'EOF_CONFIG'
[pi5]
arm_64bit=1
dtoverlay=bcm2712d0
EOF_CONFIG

cat > "$WORK/grub-version.cfg" <<'EOF_GRUB'
menuentry "test" {
    set boot_opts="boot=live rootdelay=5 noautologin net.ifnames=0 biosdevname=0 vyos-union=/boot/2026.08.19-test"
    linux "/boot/2026.08.19-test/vmlinuz" ${boot_opts}
    initrd "/boot/2026.08.19-test/initrd.img"
}
EOF_GRUB

cat > "$WORK/base.dts" <<'EOF_DTS'
/dts-v1/;

/ {
    compatible = "raspberrypi,5-model-b", "brcm,bcm2712";
    #address-cells = <2>;
    #size-cells = <2>;

    soc@107c000000 {
        compatible = "simple-bus";
        #address-cells = <1>;
        #size-cells = <1>;

        gio: gpio@7d508500 {
            compatible = "brcm,bcm2712-gpio";
            reg = <0x7d508500 0x40>;
        };

        gio_aon: gpio@7d517c00 {
            compatible = "brcm,bcm2712-aon-gpio";
            reg = <0x7d517c00 0x40>;
        };

        pinctrl: pinctrl@7d504100 {
            compatible = "brcm,bcm2712-pinctrl";
            reg = <0x7d504100 0x20>;
        };

        pinctrl_aon: pinctrl@7d510700 {
            compatible = "brcm,bcm2712-aon-pinctrl";
            reg = <0x7d510700 0x1c>;
        };

        uart10: serial@7d001000 {
            compatible = "arm,pl011";
            reg = <0x7d001000 0x200>;
        };

        mmc@1100000 {
            compatible = "brcm,bcm2712-sdhci";
            reg = <0x01100000 0x1000>;
            #address-cells = <1>;
            #size-cells = <0>;

            wifi@1 {
                compatible = "brcm,bcm4329-fmac";
                reg = <1>;
            };
        };
    };
};
EOF_DTS

dtc -@ -I dts -O dtb \
    -o "$WORK/artifacts/dtb/broadcom/bcm2712-rpi-5-b-test.dtb" \
    "$WORK/base.dts"

printf 'kernel-payload\n' > "$WORK/artifacts/Image"
printf 'initrd-payload\n' > "$WORK/version/initrd.img"

cat > "$WORK/boot-manifest.env" <<'EOF_MANIFEST'
BOOT_FDT_FILE=broadcom/bcm2712-rpi-5-b-test.dtb
EOF_MANIFEST

"$ROOT/tools/firmware-providers/raspberrypi-native/finalize.sh" \
    raspberry-pi-5 \
    "$WORK/firmware" \
    "$WORK/version" \
    "$WORK/artifacts" \
    "$WORK/grub-version.cfg" \
    "$WORK/boot-manifest.env"

grep -Eq '^\[all\]$' "$WORK/firmware/config.txt"
grep -Eq '^kernel=vmlinuz$' "$WORK/firmware/config.txt"
grep -Eq '^initramfs initrd\.img followkernel$' "$WORK/firmware/config.txt"
grep -Eq '^device_tree=bcm2712-rpi-5-b-test\.dtb$' "$WORK/firmware/config.txt"
[[ "$(grep -Ec '^dtoverlay=bcm2712d0$' "$WORK/firmware/config.txt")" -eq 1 ]]
grep -Eq '(^| )boot=live( |$)' "$WORK/firmware/cmdline.txt"
grep -Eq '(^| )vyos-union=/boot/2026\.08\.19-test( |$)' "$WORK/firmware/cmdline.txt"
grep -Eq '(^| )console=ttyAMA10,115200( |$)' "$WORK/firmware/cmdline.txt"
cmp -s "$WORK/artifacts/Image" "$WORK/firmware/vmlinuz"
cmp -s "$WORK/version/initrd.img" "$WORK/firmware/initrd.img"
test -s "$WORK/firmware/overlays/bcm2712d0.dtbo"

[[ "$(fdtget -t bx \
    "$WORK/firmware/bcm2712-rpi-5-b-test.dtb" \
    /soc@107c000000/mmc@1100000/wifi@1 \
    local-mac-address)" == "0 0 0 0 0 0" ]]

[[ "$(fdtget -t s \
    "$WORK/firmware/bcm2712-rpi-5-b-test.dtb" \
    /aliases \
    wifi0)" == "/soc@107c000000/mmc@1100000/wifi@1" ]]

fdtget \
    "$WORK/firmware/bcm2712-rpi-5-b-test.dtb" \
    /__overrides__ \
    wifiaddr >/dev/null

echo "PASS: raspberrypi-native finalize contract"

PACKAGE_ROOT="$WORK/package-root"
PACKAGE="$WORK/firmware-brcm80211-test_all.deb"
ROOTFS="$WORK/rootfs"
BOOT_DIR="$WORK/boot"

mkdir -p \
    "$PACKAGE_ROOT/DEBIAN" \
    "$PACKAGE_ROOT/usr/lib/firmware/brcm" \
    "$PACKAGE_ROOT/usr/lib/firmware/cypress" \
    "$PACKAGE_ROOT/usr/share/doc/firmware-brcm80211" \
    "$ROOTFS" \
    "$BOOT_DIR/artifacts"

cat > "$PACKAGE_ROOT/DEBIAN/control" <<'EOF_CONTROL'
Package: firmware-brcm80211-test
Version: 1
Architecture: all
Maintainer: Test <test@example.invalid>
Description: Minimal BCM43455 provider test fixture
EOF_CONTROL

printf 'firmware\n' \
    > "$PACKAGE_ROOT/usr/lib/firmware/cypress/cyfmac43455-sdio.bin"
printf 'clm\n' \
    > "$PACKAGE_ROOT/usr/lib/firmware/cypress/cyfmac43455-sdio.clm_blob"
printf 'boardrev=0x1101\n' \
    > "$PACKAGE_ROOT/usr/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,4-model-b.txt"
printf 'Redistribution test fixture\n' \
    > "$PACKAGE_ROOT/usr/share/doc/firmware-brcm80211/copyright"

ln -s ../cypress/cyfmac43455-sdio.bin \
    "$PACKAGE_ROOT/usr/lib/firmware/brcm/brcmfmac43455-sdio.bin"
ln -s ../cypress/cyfmac43455-sdio.clm_blob \
    "$PACKAGE_ROOT/usr/lib/firmware/brcm/brcmfmac43455-sdio.clm_blob"
ln -s brcmfmac43455-sdio.raspberrypi,4-model-b.txt \
    "$PACKAGE_ROOT/usr/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.txt"

dpkg-deb --build "$PACKAGE_ROOT" "$PACKAGE" >/dev/null
cp "$PACKAGE" "$BOOT_DIR/artifacts/$(basename "$PACKAGE")"

PACKAGE_SHA256="$(sha256sum "$PACKAGE" | awk '{print $1}')"

cat > "$BOOT_DIR/raspberrypi-template.env" <<EOF_TEMPLATE
RPI_WLAN_FIRMWARE_ASSET=$(basename "$PACKAGE")
RPI_WLAN_FIRMWARE_SHA256=$PACKAGE_SHA256
EOF_TEMPLATE

printf 'FIRMWARE_PROVIDER=raspberrypi-native\n' \
    > "$BOOT_DIR/boot-manifest.env"

bash "$ROOT/tools/firmware-providers/raspberrypi-native/rootfs.sh" \
    raspberry-pi-5 \
    "$ROOTFS" \
    "$BOOT_DIR" \
    "$BOOT_DIR/boot-manifest.env"

test -s "$ROOTFS/usr/lib/firmware/cypress/cyfmac43455-sdio.bin"
test -s "$ROOTFS/usr/lib/firmware/cypress/cyfmac43455-sdio.clm_blob"
test -L "$ROOTFS/usr/lib/firmware/brcm/brcmfmac43455-sdio.bin"
test -L "$ROOTFS/usr/lib/firmware/brcm/brcmfmac43455-sdio.clm_blob"
test -L "$ROOTFS/usr/lib/firmware/brcm/brcmfmac43455-sdio.raspberrypi,5-model-b.txt"
test -s "$ROOTFS/usr/share/doc/firmware-brcm80211/copyright"

echo "PASS: raspberrypi-native rootfs firmware contract"
