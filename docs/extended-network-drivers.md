# Optional Extended Network support

The board builder always starts with the official VyOS ARM64 kernel
configuration and then adds the drivers required by the selected board. The
optional **Extended Network** profile is a third, independent runtime layer:

1. Stock VyOS drivers
2. Board-required drivers derived from the board model, DTB and reference
   metadata
3. Optional Extended Network drivers and their firmware

Interactive builds ask after the board has been selected:

```text
Include common additional network drivers and firmware? [y/N]
```

The default is **No**. Non-interactive builds use `EXTENDED_NETWORK=no`
unless explicitly overridden. GitHub Actions exposes the same setting as the
`extended_network` workflow input.

## Security and resource notice

The optional profile is a convenience-oriented, intentionally incomplete
collection for common ARM SBC, router, M.2 and USB networking hardware. Most
of its components will not be relevant to any single system. Enabling it
increases image size; modules loaded for detected hardware consume memory,
and additional loadable driver code and firmware increase the system's attack
surface. Industrial and security-sensitive deployments should use a selective
driver/firmware set instead.

Only drivers available in the selected upstream/VyOS Linux source tree are
considered. The profile does not download or build third-party Wi-Fi DKMS
drivers.

## Curated driver catalog

Every request is made as `=m`. Existing stock/board values (`=y` or `=m`) are
preserved and never demoted. Missing symbols, unsatisfied optional
dependencies, or symbols which Kconfig cannot keep as modules are reported as
`SKIPPED`; they do not fail the board build.

| Category | Driver/config families | Typical hardware | Firmware namespace or source |
|---|---|---|---|
| Realtek Wi-Fi, PCIe | RTW88 8821CE/8822BE/8822CE/8814AE; RTW89 8851BE/8852AE/8852BE/8852BTE/8852CE/8922AE | Common M.2/PCIe Realtek adapters | `rtw88/`, `rtw89/` via module metadata |
| Realtek Wi-Fi, USB | Mainline RTW88 8723DU/8812AU/8814AU/8821AU/8821CU/8822BU/8822CU; RTW89 8851BU/8852BU when available | Mainline-supported USB adapters | `rtw88/`, `rtw89/` via module metadata |
| MediaTek Wi-Fi | `MT7921E/U`, `MT7925E/U`, `MT7996E` | MT7921/MT7922/MT7925/MT7996 adapters | `mediatek/` via module metadata |
| Qualcomm/Atheros Wi-Fi | `ATH11K_PCI`, `ATH12K_PCI` | Wi-Fi 6/6E/7 PCIe adapters | `ath11k/`, `ath12k/`; board/calibration data may still be device-specific |
| Intel Wi-Fi | `IWLWIFI`, `IWLMVM` | AX-series PCIe/M.2 adapters | `intel/` and `iwlwifi-*` via module metadata |
| NXP/Marvell Wi-Fi | `MWIFIEX_SDIO`, `MWIFIEX_PCIE`, `MWIFIEX_USB` | SDIO, PCIe and USB modules | `mrvl/` via module metadata |
| PCIe/M.2 WWAN | MHI PCI generic host, MHI net/control/MBIM, QRTR over MHI | Qualcomm/SDX-based M.2 modems | Firmware requirements reported by the built MHI modules; modem-internal firmware is vendor/device-specific |
| Intel Ethernet | `IXGBE`, `IXGBEVF`, `I40E`, `I40EVF`, `ICE` | Intel 10/25/40/100GbE adapters | Module-declared firmware from the VyOS-pinned source |
| Aquantia USB Ethernet | `USB_NET_AQC111` | AQC111U-based USB 2.5/5GbE adapters | Module-declared firmware from the VyOS-pinned source |

USB modem support already present in stock VyOS (MBIM, QMI, NCM, `option`,
Sierra and related USB serial/network drivers) is not duplicated. MHI endpoint
mode, debug/test drivers and boot/controller infrastructure are also excluded.

The machine-readable source of truth is:

- `profiles/extended-network-drivers.txt` — optional Kconfig requests
- `profiles/extended-network-modules.tsv` — symbol-to-module/category mapping
- `profiles/extended-network-firmware-supplements.txt` — proven exceptions
- `profiles/baseline-network-modules.txt` — existing modules whose firmware is
  staged even when Extended Network is disabled

## Firmware policy

Firmware is not maintained as a large static file list. After the final kernel
and module tree have been built, the builder runs `modinfo -F firmware` for:

- relevant existing baseline modules; and
- newly enabled Extended Network modules.

The referenced files are copied from the exact `linux-firmware` source and
revision declared by the checked-out VyOS
`scripts/package-build/linux-kernel/package.toml`. The current resolved commit
is recorded in every build manifest. Module-specific supplement globs are used
only for a proven requirement which `modinfo` cannot express.

The baseline and optional closures remain separate. For example, `r8169` is
already a stock driver and therefore is **not** an Extended Network driver;
its declared `rtl_nic/` firmware is staged through the baseline path.

Missing runtime firmware is warning-only and is recorded precisely. Extended
Network modules are not added to the initramfs merely because the option is
enabled.

## Per-build audit artifacts

Each candidate publishes:

- `extended-network-report.txt`
- `network-firmware-manifest.json`
- `required-firmware.txt`
- `required-firmware-baseline.txt`
- `required-firmware-extended.txt`
- `installed-firmware.txt`
- `missing-firmware.txt`

These files show what was requested, already present, enabled, skipped,
installed or missing for that exact kernel and VyOS firmware pin.
