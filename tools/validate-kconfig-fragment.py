#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


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


def classify(want, got):
    if want == got:
        return "OK"

    if got == "n":
        return "MISSING"

    if want == "y" and got == "m":
        return "DOWNGRADE"

    if want == "m" and got == "y":
        return "UPGRADE"

    return "CHANGED"


def main():
    parser = argparse.ArgumentParser(
        description="Validate requested Kconfig values against final .config"
    )
    parser.add_argument("--requested", required=True)
    parser.add_argument("--final", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    requested = read_config(args.requested)
    final = read_config(args.final)

    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    groups = {
        "OK": [],
        "DOWNGRADE": [],
        "UPGRADE": [],
        "MISSING": [],
        "CHANGED": [],
    }

    report = []

    for symbol in sorted(requested):
        want = requested[symbol]
        got = final.get(symbol, "n")

        state = classify(want, got)
        groups[state].append(symbol)

        report.append(
            f"{state:10} {symbol:45} requested={want:3} final={got}"
        )

    (out / "report.txt").write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    for state, symbols in groups.items():
        filename = state.lower() + ".txt"
        (out / filename).write_text(
            "\n".join(symbols) + ("\n" if symbols else ""),
            encoding="utf-8"
        )

    print("Kconfig fragment validation")
    print("---------------------------")
    print(f"Requested: {len(requested)}")

    for state in ["OK", "DOWNGRADE", "UPGRADE", "MISSING", "CHANGED"]:
        print(f"{state:10}: {len(groups[state])}")

    print()
    print(f"Report: {out / 'report.txt'}")


if __name__ == "__main__":
    main()
