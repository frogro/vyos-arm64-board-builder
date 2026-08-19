#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path


#
# Some boot-critical Linux subsystems instantiate DT devices before the
# conventional platform-driver path is available.  Those drivers therefore
# have no struct of_device_id referenced by .of_match_table.  Keep this list
# limited to real early OF registration APIs whose second argument is a DT
# compatible string.
#
EARLY_OF_DECLARE_RE = re.compile(
    r"""
    \b
    (?P<macro>
        IRQCHIP_DECLARE
        | TIMER_OF_DECLARE
        | CLK_OF_DECLARE_DRIVER
        | CLK_OF_DECLARE
        | IOMMU_OF_DECLARE
        | RESERVEDMEM_OF_DECLARE
    )
    \s*\(
    \s*[A-Za-z_][A-Za-z0-9_]*\s*,
    \s*"(?P<compatible>[^"]+)"
    """,
    re.S | re.X,
)


def declarations_in_text(text: str) -> list[tuple[str, str]]:
    return [
        (
            match.group("compatible"),
            match.group("macro"),
        )
        for match in EARLY_OF_DECLARE_RE.finditer(text)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Index early Linux OF driver declarations by compatible string."
        )
    )

    parser.add_argument(
        "--kernel",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    kernel = Path(args.kernel).resolve()
    output = Path(args.output)
    rows = set()

    for subtree in ("drivers", "sound"):
        root = kernel / subtree

        if not root.is_dir():
            continue

        for source in root.rglob("*.c"):
            try:
                text = source.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                continue

            relative = source.relative_to(kernel).as_posix()

            for compatible, macro in declarations_in_text(text):
                rows.add(
                    (
                        compatible,
                        relative,
                        macro,
                    )
                )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open("w", encoding="utf-8") as f:
        for compatible, source, macro in sorted(rows):
            print(
                compatible,
                source,
                macro,
                sep="\t",
                file=f,
            )


if __name__ == "__main__":
    main()
