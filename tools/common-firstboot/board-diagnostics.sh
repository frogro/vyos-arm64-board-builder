#!/usr/bin/env bash
# Read-only support bundle on stdout. Does not include config.boot or credentials.
set -u
printf '=== Board boot and image identity ===\n'
uname -a
cat /proc/cmdline
cat /usr/share/vyos-arm64-board-builder/boot-provider.json 2>/dev/null || true
findmnt -o TARGET,SOURCE,FSTYPE / /boot /usr/lib/live/mount/persistence 2>/dev/null || true
printf '\n=== Live Device Tree interrupt coherency ===\n'
python3 - <<'PY'
from pathlib import Path
root = Path('/sys/firmware/devicetree/base')
if not root.is_dir():
    print('Live Device Tree unavailable')
else:
    for prop in root.rglob('compatible'):
        compatible = prop.read_bytes().replace(b'\0', b' ').decode(errors='replace')
        if any(value in compatible for value in ('gic-v3', 'gic-v3-its')):
            node = prop.parent
            print(str(node.relative_to(root)), compatible,
                  'dma-noncoherent=' + str((node / 'dma-noncoherent').exists()),
                  'dma-coherent=' + str((node / 'dma-coherent').exists()))
PY
printf '\n=== PCIe and Ethernet ===\n'
lspci -nnk 2>/dev/null || true
ip -br link
for p in /sys/class/net/eth*; do
    [[ -e "$p" ]] || continue
    iface="${p##*/}"
    printf '\n%s device=%s\n' "$iface" "$(readlink -f "$p/device")"
    ethtool "$iface" 2>/dev/null || true
    ethtool -i "$iface" 2>/dev/null || true
done
printf '\n=== Serial service ===\n'
systemctl --no-pager --full status serial-getty@ttyS2.service 2>/dev/null || true
printf '\n=== Relevant kernel messages ===\n'
journalctl -k -b --no-pager | grep -Ei 'ITS|GIC|pcie|r8169|rtl8125|timeout|dma.*coher' || true
