#!/usr/bin/env python3
"""Validate promoted model requirements against generated build artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


CONFIG_RE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")


def read_config(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = CONFIG_RE.fullmatch(line.strip())
        if match:
            result[match.group(1)] = match.group(2)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--kernel-config", type=Path, required=True)
    parser.add_argument("--dtb-root", type=Path, required=True)
    args = parser.parse_args()

    try:
        model = json.loads(args.model.read_text(encoding="utf-8"))
        requirements = model.get("requirements", {})
        fixture_relative = requirements.get("hardware_config")
        if not isinstance(fixture_relative, str) or not fixture_relative:
            raise ValueError("model has no requirements.hardware_config")
        fixture = (args.root / fixture_relative).resolve()
        root = args.root.resolve()
        if root not in fixture.parents:
            raise ValueError("hardware-config fixture escapes repository root")
        expected = read_config(fixture)
        actual = read_config(args.kernel_config)
        if not expected:
            raise ValueError(f"model hardware fixture is empty: {fixture}")
        failures = [
            f"{name}: expected {value}, got {actual.get(name, 'missing')}"
            for name, value in sorted(expected.items())
            if actual.get(name) != value
        ]
        dtb_relative = model.get("device_tree", {}).get("boot_fdt_file")
        if not isinstance(dtb_relative, str) or not dtb_relative.endswith(".dtb"):
            raise ValueError("model has no valid device_tree.boot_fdt_file")
        dtb = args.dtb_root / dtb_relative
        if not dtb.is_file() or dtb.stat().st_size == 0:
            failures.append(f"model DTB missing: {dtb}")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1

    print(f"PASS: {model['model']} model requirements")
    print(f"Required config symbols: {len(expected)}")
    print(f"Required DTB: {dtb_relative}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
