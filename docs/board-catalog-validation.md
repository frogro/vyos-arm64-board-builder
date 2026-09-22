# Automated board-catalog validation

The Armbian board scanner and the VyOS image builder remain independent. The
builder consumes their stable profile contract through `tools/board_catalog.py`.
No board-by-board manual comparison is part of the normal catalog workflow.

Run one validation pass over a complete scanner archive:

```bash
./tools/validate-catalog.sh /path/to/catalog.zip 6.18.44
```

The command checks every indexed `BOARD × KERNEL_TARGET` profile and writes a
machine-readable report to `work/catalog-validation-report.json`. A different
report path can be supplied as the third argument.

## Automated for the complete catalog

- inventory/index/profile coverage and count consistency;
- full Armbian commit provenance and board-source identity;
- portable `config.env` parsing, including multiline target maps;
- board, target, architecture, status and provider agreement;
- kernel major/minor and advertised target consistency;
- single-DTB versus multi-model DTB contracts;
- active U-Boot versus inactive-default metadata;
- Raspberry Pi native-boot invariants;
- model-to-Armbian-BOARD mapping;
- exact AUTO hardware-reference selection for the supplied VyOS kernel;
- `current → edge → vendor → remaining advertised targets` priority among
  exact kernel-line matches;
- fail-closed reporting when no exact kernel line exists.

`HW_REFERENCE=<target>` is the developer-only escape hatch. Its use is recorded
as `developer-override`; it is not presented as a normal installer question.

## Build-time checks for a promoted model

A model profile can add the concrete DTB and mandatory Kconfig fixture that a
multi-model Armbian profile cannot provide. The Pi 5 profile maps
`raspberry-pi-5` to Armbian `rpi4b`, selects
`broadcom/bcm2712-rpi-5-b.dtb`, rejects U-Boot and requires the
`raspberrypi-native` boot provider. The generic config validator requires the
boot-critical dependency closure to remain built-in and permits runtime
hardware as either built-in or modules. The model check then verifies that its
mandatory hardware remains available and that the concrete DTB exists before
image assembly.

## Requires real hardware

Static metadata and image inspection cannot prove that a physical board boots,
that its PHY is wired correctly or that every storage/network peripheral works.
Those results remain separate `hardware-proven` evidence. They do not require
repeating the catalog audit manually for every board.
