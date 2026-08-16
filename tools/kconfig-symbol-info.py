#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


CONFIG_RE = re.compile(r'^(?:config|menuconfig)\s+([A-Za-z0-9_]+)\s*$')
SELECT_RE = re.compile(r'^\s*select\s+([A-Za-z0-9_]+)(?:\s+if\s+(.+))?\s*$')
DEPENDS_RE = re.compile(r'^\s*depends on\s+(.+)\s*$')


def scan_kconfig(kernel):
    defs = {}
    reverse_select = {}

    for path in Path(kernel).rglob("Kconfig*"):
        if not path.is_file():
            continue

        try:
            lines = path.read_text(
                encoding="utf-8",
                errors="ignore"
            ).splitlines()
        except OSError:
            continue

        current = None
        block = []

        def store(symbol, block_lines):
            if not symbol:
                return

            entry = defs.setdefault(symbol, {
                "locations": set(),
                "depends": [],
                "selects": [],
                "prompt": False,
            })

            entry["locations"].add(str(path))

            for line in block_lines:
                stripped = line.strip()

                if re.match(
                    r'^(bool|tristate|string|int|hex)\s+"',
                    stripped
                ):
                    entry["prompt"] = True

                m = DEPENDS_RE.match(line)
                if m:
                    entry["depends"].append(m.group(1))

                m = SELECT_RE.match(line)
                if m:
                    target = m.group(1)
                    cond = m.group(2)

                    entry["selects"].append((target, cond))
                    reverse_select.setdefault(target, []).append(
                        (symbol, cond)
                    )

        for line in lines:
            m = CONFIG_RE.match(line)

            if m:
                store(current, block)
                current = m.group(1)
                block = [line]
                continue

            if current:
                if re.match(
                    r'^(config|menuconfig)\s+',
                    line
                ):
                    store(current, block)
                    current = None
                    block = []
                else:
                    block.append(line)

        store(current, block)

    return defs, reverse_select


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel", required=True)
    parser.add_argument("symbols", nargs="+")
    args = parser.parse_args()

    defs, reverse_select = scan_kconfig(args.kernel)

    for symbol in args.symbols:
        symbol = symbol.removeprefix("CONFIG_")

        print("=" * 72)
        print(f"CONFIG_{symbol}")

        data = defs.get(symbol)

        if not data:
            print("definition: NOT FOUND")
            continue

        print(f"user-visible prompt: {'yes' if data['prompt'] else 'no'}")

        for loc in sorted(data["locations"]):
            print(f"Kconfig: {loc}")

        if data["depends"]:
            print("depends:")
            for expr in data["depends"]:
                print(f"  {expr}")

        if data["selects"]:
            print("selects:")
            for target, cond in data["selects"]:
                text = f"CONFIG_{target}"
                if cond:
                    text += f" if {cond}"
                print(f"  {text}")

        incoming = reverse_select.get(symbol, [])

        if incoming:
            print("selected by:")
            for source, cond in sorted(incoming):
                text = f"CONFIG_{source}"
                if cond:
                    text += f" if {cond}"
                print(f"  {text}")

        print()


if __name__ == "__main__":
    main()
