#!/usr/bin/env python3

from pathlib import Path

p = Path("cache/vyos-build/scripts/image-build/raw_image.py")

if not p.is_file():
    raise SystemExit(f"ERROR: VyOS raw image builder not found: {p}")

s = p.read_text()

old = """    print('I: Installing GRUB to the disk image')
    grub.install(con.loop_device, f'/boot/', f'/boot/efi', chroot=con.squash_dir)
"""

new = """    print('I: Installing GRUB to the disk image')

    if con.build_config.get("architecture") == "arm64":
        print('I: ARM64 target detected - installing ARM64 EFI GRUB only')
        cmd(
            f"chroot {con.squash_dir} "
            f"grub-install --no-floppy --recheck "
            f"--target=arm64-efi "
            f"--force-extra-removable "
            f"--boot-directory=/boot/ "
            f"--efi-directory=/boot/efi "
            f"--bootloader-id=VyOS "
            f"--uefi-secure-boot"
        )
    else:
        raise RuntimeError(
            f"Unsupported architecture for ARM64 board builder: "
            f"{con.build_config.get('architecture')}"
        )
"""

if old not in s:
    raise SystemExit(
        "ERROR: expected upstream VyOS grub.install block not found; "
        "upstream source probably changed"
    )

p.write_text(s.replace(old, new, 1))

print("OK: VyOS raw-image builder patched for ARM64-only GRUB installation")
