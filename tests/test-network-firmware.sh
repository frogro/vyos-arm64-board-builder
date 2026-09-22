#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p \
    "$WORK/bin" \
    "$WORK/firmware-source/rtl_nic" \
    "$WORK/firmware-source/mediatek" \
    "$WORK/vyos/scripts/package-build/linux-kernel" \
    "$WORK/modules/lib/modules/test-kernel" \
    "$WORK/input"

printf 'realtek firmware\n' \
    > "$WORK/firmware-source/rtl_nic/rtl8125b-2.fw"
printf 'mediatek firmware\n' \
    > "$WORK/firmware-source/mediatek/mt7922-test.bin"
printf 'mediatek common firmware\n' \
    > "$WORK/firmware-source/mediatek/mt7922-common.bin"

git -C "$WORK/firmware-source" init --quiet
git -C "$WORK/firmware-source" config user.email test@example.invalid
git -C "$WORK/firmware-source" config user.name test
git -C "$WORK/firmware-source" add rtl_nic mediatek
git -C "$WORK/firmware-source" commit --quiet -m fixture
git -C "$WORK/firmware-source" tag test-pin

cat > "$WORK/vyos/scripts/package-build/linux-kernel/package.toml" <<EOF
[[packages]]
name = "linux-firmware"
commit_id = "test-pin"
scm_url = "file://$WORK/firmware-source"
EOF

cat > "$WORK/bin/modinfo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

field=""
module="${!#}"

while (($#)); do
    case "$1" in
        -F)
            field="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

case "$field:$module" in
    filename:r8169)
        echo kernel/drivers/net/ethernet/realtek/r8169.ko.xz
        ;;
    filename:mt7921e)
        echo kernel/drivers/net/wireless/mediatek/mt7921e.ko.xz
        ;;
    filename:mt7921_common)
        echo kernel/drivers/net/wireless/mediatek/mt7921_common.ko.xz
        ;;
    firmware:r8169)
        echo rtl_nic/rtl8125b-2.fw
        ;;
    firmware:mt7921e)
        echo mediatek/mt7922-test.bin
        ;;
    firmware:mt7921_common)
        echo mediatek/mt7922-common.bin
        ;;
    depends:mt7921e)
        echo mt7921_common
        ;;
    *)
        exit 1
        ;;
esac
EOF
chmod +x "$WORK/bin/modinfo"

cat > "$WORK/input/resolver.json" <<'EOF'
{
  "enabled": true,
  "entries": [
    {
      "symbol": "CONFIG_MT7921E",
      "base_value": "n",
      "final_value": "m",
      "status": "enabled"
    }
  ]
}
EOF

cat > "$WORK/input/modules.tsv" <<'EOF'
wifi-pcie	CONFIG_MT7921E	mt7921e	MediaTek MT7922
EOF
printf 'r8169\n' > "$WORK/input/baseline.txt"
printf '# none\n' > "$WORK/input/supplements.txt"

PATH="$WORK/bin:$PATH" \
python3 "$ROOT/tools/stage-network-firmware.py" \
    --vyos-tree "$WORK/vyos" \
    --modules-root "$WORK/modules" \
    --kernel-release test-kernel \
    --resolver-report "$WORK/input/resolver.json" \
    --module-catalog "$WORK/input/modules.tsv" \
    --baseline-modules "$WORK/input/baseline.txt" \
    --supplements "$WORK/input/supplements.txt" \
    --cache-dir "$WORK/cache/linux-firmware" \
    --output-dir "$WORK/output"

test -f "$WORK/output/root/usr/lib/firmware/rtl_nic/rtl8125b-2.fw"
test -f "$WORK/output/root/usr/lib/firmware/mediatek/mt7922-test.bin"
test -f "$WORK/output/root/usr/lib/firmware/mediatek/mt7922-common.bin"
grep -Fq $'baseline\tr8169\trtl_nic/rtl8125b-2.fw' \
    "$WORK/output/installed-firmware.txt"
grep -Fq $'extended\tmt7921e\tmediatek/mt7922-test.bin' \
    "$WORK/output/installed-firmware.txt"
grep -Fq $'extended\tmt7921_common\tmediatek/mt7922-common.bin' \
    "$WORK/output/installed-firmware.txt"
test ! -s "$WORK/output/missing-firmware.txt"

mkdir -p "$WORK/rootfs"
bash "$ROOT/tools/install-network-firmware.sh" \
    test-board \
    "$WORK/rootfs" \
    "$WORK/output"

test -f "$WORK/rootfs/usr/lib/firmware/rtl_nic/rtl8125b-2.fw"
test -f \
    "$WORK/rootfs/usr/share/doc/vyos-arm64-board-builder/network/network-firmware-manifest.json"

echo "PASS: network firmware closure and rootfs installation"
