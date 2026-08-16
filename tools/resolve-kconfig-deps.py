#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


CONFIG_RE = re.compile(r'^(?:menuconfig|config)\s+([A-Za-z0-9_]+)\s*$')
DEPENDS_RE = re.compile(r'^\s*depends on\s+(.+?)\s*$')
SELECT_RE = re.compile(r'^\s*select\s+([A-Za-z0-9_]+)(?:\s+if\s+(.+))?\s*$')
IMPLY_RE = re.compile(r'^\s*imply\s+([A-Za-z0-9_]+)(?:\s+if\s+(.+))?\s*$')


def read_config(path):
    values = {}

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            m = re.match(r'^(CONFIG_[A-Za-z0-9_]+)=(.*)$', line)
            if m:
                values[m.group(1)] = m.group(2)
                continue

            m = re.match(r'^# (CONFIG_[A-Za-z0-9_]+) is not set$', line)
            if m:
                values[m.group(1)] = "n"

    return values


def find_symbol_blocks(kernel):
    symbols = {}

    for path in kernel.rglob("Kconfig*"):
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

        def store():
            if current is None:
                return

            entry = symbols.setdefault(
                current,
                {
                    "locations": [],
                    "depends": [],
                    "selects": [],
                    "implies": [],
                },
            )

            entry["locations"].append(str(path))

            for item in block:
                m = DEPENDS_RE.match(item)
                if m:
                    entry["depends"].append(m.group(1))

                m = SELECT_RE.match(item)
                if m:
                    entry["selects"].append(
                        (m.group(1), m.group(2))
                    )

                m = IMPLY_RE.match(item)
                if m:
                    entry["implies"].append(
                        (m.group(1), m.group(2))
                    )

        for line in lines:
            m = CONFIG_RE.match(line)

            if m:
                store()
                current = m.group(1)
                block = [line]
            elif current is not None:
                # Stop when another major Kconfig statement starts.
                if re.match(
                    r'^(menu|endmenu|choice|endchoice|if|endif|source|rsource|osource)\b',
                    line
                ):
                    store()
                    current = None
                    block = []
                else:
                    block.append(line)

        store()

    return symbols


def extract_symbols(expr):
    raw = re.findall(r'\b[A-Z][A-Z0-9_]+\b', expr)

    ignored = {
        "Y",
        "M",
        "N",
    }

    return [
        symbol
        for symbol in raw
        if symbol not in ignored
    ]


def state(config, symbol):
    return config.get(f"CONFIG_{symbol}", "n")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect Kconfig dependencies for unresolved requested symbols"
    )

    parser.add_argument("--kernel", required=True)
    parser.add_argument("--requested", required=True)
    parser.add_argument("--final", required=True)
    parser.add_argument("--output", required=True)

    args = parser.parse_args()

    kernel = Path(args.kernel)
    out = Path(args.output)

    out.mkdir(parents=True, exist_ok=True)

    requested = read_config(args.requested)
    final = read_config(args.final)

    symbol_db = find_symbol_blocks(kernel)

    unresolved = []

    for name, want in requested.items():
        got = final.get(name, "n")

        if got != want:
            unresolved.append(
                name.removeprefix("CONFIG_")
            )

    lines = []
    direct_missing = set()

    for symbol in sorted(unresolved):
        want = requested.get(f"CONFIG_{symbol}", "n")
        got = final.get(f"CONFIG_{symbol}", "n")

        lines.append("=" * 72)
        lines.append(f"CONFIG_{symbol}")
        lines.append(f"requested={want} final={got}")

        data = symbol_db.get(symbol)

        if not data:
            lines.append("Kconfig definition: NOT FOUND")
            lines.append("")
            continue

        lines.append(
            "Kconfig: " + ", ".join(sorted(set(data["locations"])))
        )

        if data["depends"]:
            lines.append("depends on:")

            for expr in data["depends"]:
                lines.append(f"  {expr}")

                for dep in extract_symbols(expr):
                    dep_state = state(final, dep)

                    lines.append(
                        f"    CONFIG_{dep}={dep_state}"
                    )

                    if dep_state == "n":
                        direct_missing.add(dep)

        else:
            lines.append("depends on: none")

        if data["selects"]:
            lines.append("selects:")

            for dep, cond in data["selects"]:
                if cond:
                    lines.append(
                        f"  CONFIG_{dep} if {cond}"
                    )
                else:
                    lines.append(
                        f"  CONFIG_{dep}"
                    )

        if data["implies"]:
            lines.append("implies:")

            for dep, cond in data["implies"]:
                if cond:
                    lines.append(
                        f"  CONFIG_{dep} if {cond}"
                    )
                else:
                    lines.append(
                        f"  CONFIG_{dep}"
                    )

        lines.append("")

    report = out / "dependency-report.txt"
    report.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    missing_file = out / "direct-missing-dependencies.txt"
    missing_file.write_text(
        "\n".join(
            f"CONFIG_{x}"
            for x in sorted(direct_missing)
        ) + ("\n" if direct_missing else ""),
        encoding="utf-8"
    )

    print("Kconfig dependency inspection")
    print("-----------------------------")
    print(f"Unresolved requested symbols: {len(unresolved)}")
    print(f"Direct missing dependencies:  {len(direct_missing)}")
    print()
    print(f"Report: {report}")
    print(f"Missing dependencies: {missing_file}")


if __name__ == "__main__":
    main()
