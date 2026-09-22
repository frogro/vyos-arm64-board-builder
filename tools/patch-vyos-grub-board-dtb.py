#!/usr/bin/env python3
"""Persist a board-specific DTB in VyOS per-version GRUB entries."""

from __future__ import annotations

import argparse
from pathlib import Path, PurePosixPath


TEMPLATE_REL = Path(
    "usr/share/vyos/templates/grub/grub_vyos_version.j2"
)

LINUX_LINE = '    linux "/boot/{{ version_name }}/vmlinuz" ${boot_opts}'


def validate_boot_fdt_file(value: str) -> str:
    if not value or value != value.strip():
        raise SystemExit(
            "BOOT_FDT_FILE must not be empty or contain outer whitespace"
        )

    if any(ch in value for ch in ('\x00', '\r', '\n', '"')):
        raise SystemExit("BOOT_FDT_FILE contains invalid characters")

    path = PurePosixPath(value)

    if path.is_absolute():
        raise SystemExit("BOOT_FDT_FILE must be a relative path")

    if any(part in ("", ".", "..") for part in path.parts):
        raise SystemExit(
            f"BOOT_FDT_FILE must be normalized: {value!r}"
        )

    if path.as_posix() != value:
        raise SystemExit(
            f"BOOT_FDT_FILE must use normalized POSIX syntax: {value!r}"
        )

    return value


def patch_grub_version_template(
    rootfs: Path,
    boot_fdt_file: str,
) -> bool:
    boot_fdt_file = validate_boot_fdt_file(boot_fdt_file)

    target = rootfs / TEMPLATE_REL

    if not target.is_file():
        raise SystemExit(
            f"VyOS GRUB version template is missing: {target}"
        )

    source = target.read_text()

    dtb_line = (
        '    devicetree '
        f'"/boot/{{{{ version_name }}}}/dtb/{boot_fdt_file}"'
    )

    existing_dtb_lines = [
        line
        for line in source.splitlines()
        if line.strip().startswith(
            'devicetree "/boot/{{ version_name }}/dtb/'
        )
    ]

    if existing_dtb_lines:
        if existing_dtb_lines == [dtb_line]:
            return False

        raise SystemExit(
            "Refusing GRUB template with an unexpected or duplicate "
            "board DTB line: "
            + "; ".join(existing_dtb_lines)
        )

    if source.count(LINUX_LINE) != 1:
        raise SystemExit(
            "VyOS GRUB version template no longer matches the expected "
            f"upstream linux line: {target}"
        )

    target.write_text(
        source.replace(
            LINUX_LINE,
            dtb_line + "\n" + LINUX_LINE,
            1,
        )
    )

    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rootfs", type=Path)
    parser.add_argument("boot_fdt_file")
    args = parser.parse_args()

    changed = patch_grub_version_template(
        args.rootfs,
        args.boot_fdt_file,
    )

    if changed:
        print(
            "Patched VyOS GRUB version template for board DTB: "
            f"{args.boot_fdt_file}"
        )
    else:
        print(
            "VyOS GRUB version template already contains board DTB: "
            f"{args.boot_fdt_file}"
        )


if __name__ == "__main__":
    main()
