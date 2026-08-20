# ARM64 initial installation and system-image updates

Each board build produces two user-facing artifacts from the same kernel,
initramfs and SquashFS payload:

- `vyos-<version>-<board>.img.xz` is the initial-installation and recovery
  image. It contains the provider boot chain, GPT, EFI and VyOS persistence
  filesystems.
- `vyos-<version>-<board>.iso` is the system-image payload consumed by the
  standard VyOS `add system image` command.

Both files have adjacent `.sha256` files whose entries use basenames, so they
can be verified from their download directory with `sha256sum -c`.

## Naming

For VyOS version `1.5-rolling-202608200300` and board `rock-5b`, the builder
publishes:

```text
Tag: 2026.08.20-0300-rolling-rock-5b
vyos-1.5-rolling-202608200300-rock-5b.img.xz
vyos-1.5-rolling-202608200300-rock-5b.iso
```

The board suffix is necessary while multiple boards share one release
repository. A future dedicated repository for one board can omit the suffix
from the tag while keeping it in asset filenames.

## Update providers

The ISO contains `board-manifest.json`, which records the board identifier,
root Device Tree compatible strings, DTB path, firmware provider and update
provider. The current stock VyOS installer ignores these additional metadata;
they are included for validation tooling and a future board-compatibility
gate.

Provider modes are:

- `efi-firmware-dtb`: firmware supplies the live Device Tree and standard
  VyOS EFI/GRUB version entries are sufficient. This path was validated on a
  Radxa ROCK 5B using EDK II.
- `grub-version-dtb`: a future post-install gate must copy the board DTB into
  the new version and add the matching GRUB `devicetree` line.
- `firmware-files`: a future post-install gate must synchronize the selected
  kernel, initramfs and DTB to a provider boot filesystem such as Raspberry
  Pi `RPICFG`.

The ISO is generated and checksum-tested for every provider so its contents
remain reproducible. Release notes warn when the selected provider still
requires a synchronization gate and the ISO must not yet be used.

## Persistence expansion

The compressed initial image deliberately remains small. On first boot,
`vyos-arm64-grow-persistence.service` resolves the mounted persistence block
device, repairs a relocated GPT backup header, extends the final persistence
partition and grows ext4 online. It does not hard-code MMC, NVMe or USB device
names. If the kernel cannot reread the expanded partition table while it is
mounted, the service leaves no completion marker and retries after the next
boot.

The image build also applies a guarded compatibility fix to VyOS
`show hardware cpu`. It preserves the existing x86 fields and adds display
fallbacks for standard ARM `/proc/cpuinfo` fields. The build fails if the
upstream VyOS implementation changes instead of applying an unverified edit.

## Validated ROCK 5B flow

The following flow was hardware-tested:

1. Write the board `.img.xz` to an SD card.
2. Expand GPT3 and ext4 to the installed medium.
3. Install the board ISO with `add system image`.
4. Keep the old system image as a GRUB fallback.
5. Boot the new default version through EDK II and VyOS EFI/GRUB.

VyOS retained the active configuration, SSH identity and network state. The
new version appeared as both `Default boot` and `Running` in
`show system image`.
