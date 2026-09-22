#!/usr/bin/env python3
"""Validate declarative generic kernel capability requirements."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_kernel_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith("CONFIG_") and "=" in line:
            symbol, value = line.split("=", 1)
            values[symbol] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            values[line[2:-11]] = "n"
    return values


def read_requirements(path: Path) -> dict[str, str]:
    requirements: dict[str, str] = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: malformed requirement")
        symbol, mode = line.split("=", 1)
        if not symbol.startswith("CONFIG_") or mode not in {
            "builtin", "available", "disabled"
        }:
            raise ValueError(f"{path}:{number}: invalid requirement: {line}")
        if symbol in requirements:
            raise ValueError(f"{path}:{number}: duplicate symbol: {symbol}")
        requirements[symbol] = mode
    return requirements


def validate(config: dict[str, str], requirements: dict[str, str]) -> list[dict[str, str]]:
    report: list[dict[str, str]] = []
    for symbol, mode in sorted(requirements.items()):
        actual = config.get(symbol, "n")
        if mode == "builtin":
            ok = actual == "y"
        elif mode == "available":
            ok = actual in {"y", "m"}
        else:
            ok = actual == "n"
        report.append({
            "symbol": symbol,
            "requirement": mode,
            "actual": actual,
            "status": "PASS" if ok else "FAIL",
        })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-config", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report-name", default="tailscale-ready")
    args = parser.parse_args()

    report = validate(
        read_kernel_config(args.kernel_config),
        read_requirements(args.requirements),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / f"{args.report_name}.json").write_text(
        json.dumps({"schema": 1, "checks": report}, indent=2) + "\n"
    )
    lines = [
        f"{item['status']}  {item['symbol']}={item['actual']} "
        f"({item['requirement']})"
        for item in report
    ]
    (args.output_dir / f"{args.report_name}.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    failures = [item for item in report if item["status"] == "FAIL"]
    if failures:
        raise SystemExit(f"{args.report_name} validation failed")


if __name__ == "__main__":
    main()
