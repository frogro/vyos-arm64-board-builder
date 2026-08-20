#!/usr/bin/env python3
"""Select the graphical Linux console in an installed VyOS GRUB tree."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ASSIGNMENT_RE = re.compile(
    r"^\s*set\s+(?P<name>console_type|console_num)=.*$"
)


def update_console_default(grub_root: Path, console_type: str) -> Path:
    defaults = grub_root / "grub.cfg.d" / "20-vyos-defaults-autoload.cfg"
    if not defaults.is_file():
        raise SystemExit(f"ERROR: VyOS GRUB defaults file is missing: {defaults}")

    lines = defaults.read_text(encoding="utf-8").splitlines()
    desired = {
        "console_type": console_type,
        "console_num": "0",
    }

    for name, value in desired.items():
        matches = [
            index
            for index, line in enumerate(lines)
            if (match := ASSIGNMENT_RE.match(line))
            and match.group("name") == name
        ]

        if len(matches) > 1:
            raise SystemExit(
                f"ERROR: multiple {name} assignments found in {defaults}"
            )

        rendered = f'set {name}="{value}"'
        if matches:
            lines[matches[0]] = rendered
        else:
            lines.append(rendered)

    defaults.write_text("\n".join(lines) + "\n", encoding="utf-8")

    installed = defaults.read_text(encoding="utf-8").splitlines()
    for name, value in desired.items():
        rendered = f'set {name}="{value}"'
        if installed.count(rendered) != 1:
            raise SystemExit(
                f"ERROR: GRUB default {name}={value} was not installed"
            )

    return defaults


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("grub_root", type=Path)
    parser.add_argument(
        "--console-type",
        choices=("tty", "ttyS", "ttyAMA"),
        default="tty",
    )
    args = parser.parse_args()

    defaults = update_console_default(args.grub_root, args.console_type)
    print(f"GRUB default console: {args.console_type}0 ({defaults})")


if __name__ == "__main__":
    main()
