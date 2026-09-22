#!/usr/bin/env python3

"""Resolve optional runtime-only network Kconfig requests fail-soft."""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


CONFIG_VALUE_RE = re.compile(r"^(CONFIG_[A-Za-z0-9_]+)=(.*)$")
CONFIG_UNSET_RE = re.compile(r"^# (CONFIG_[A-Za-z0-9_]+) is not set$")
KCONFIG_DEF_RE = re.compile(r"^(?:config|menuconfig)\s+([A-Za-z0-9_]+)\s*$")


def read_config(path):
    values = {}

    with Path(path).open(encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()
            match = CONFIG_VALUE_RE.match(line)

            if match:
                values[match.group(1)] = match.group(2)
                continue

            match = CONFIG_UNSET_RE.match(line)

            if match:
                values[match.group(1)] = "n"

    return values


def read_requests(path):
    requests = []
    seen = set()

    with Path(path).open(encoding="utf-8") as stream:
        for lineno, raw in enumerate(stream, 1):
            line = raw.strip()

            if not line or line.startswith("#"):
                continue

            match = CONFIG_VALUE_RE.match(line)

            if not match or match.group(2) != "m":
                raise SystemExit(
                    f"Invalid optional module request at {path}:{lineno}: {line}"
                )

            symbol = match.group(1)

            if symbol in seen:
                raise SystemExit(f"Duplicate optional Kconfig symbol: {symbol}")

            seen.add(symbol)
            requests.append(symbol)

    return requests


def scan_symbols(kernel):
    symbols = set()
    kernel = Path(kernel)

    for path in kernel.rglob("Kconfig*"):
        if not path.is_file():
            continue

        rel = path.relative_to(kernel)

        if len(rel.parts) >= 2 and rel.parts[:2] == ("arch", "arm"):
            continue

        try:
            lines = path.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
        except OSError:
            continue

        for line in lines:
            match = KCONFIG_DEF_RE.match(line)

            if match:
                symbols.add("CONFIG_" + match.group(1))

    return symbols


def write_config(path, values):
    lines = []

    for symbol in sorted(values):
        value = values[symbol]

        if value == "n":
            lines.append(f"# {symbol} is not set")
        else:
            lines.append(f"{symbol}={value}")

    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def kbuild_env():
    env = dict(os.environ)
    env["ARCH"] = "arm64"

    if platform.machine() != "aarch64":
        env.setdefault("CROSS_COMPILE", "aarch64-linux-gnu-")

    return env


def resolve_one(kernel, closure_tool, base_config, symbol, work):
    request = work / "request.config"
    request.write_text(f"{symbol}=m\n", encoding="utf-8")

    closure = work / "closure"

    result = subprocess.run(
        [
            str(closure_tool),
            "--kernel",
            str(kernel),
            "--base-config",
            str(base_config),
            "--requested",
            str(request),
            "--output",
            str(closure),
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    unresolved = closure / "unresolved.txt"

    if result.returncode:
        return None, f"dependency resolver exited {result.returncode}"

    if unresolved.exists() and unresolved.stat().st_size:
        reason = unresolved.read_text(encoding="utf-8").splitlines()[0]
        return None, reason

    fragment = closure / "resolved-fragment.config"

    if not fragment.is_file():
        return None, "dependency resolver produced no fragment"

    merge = work / "merge"
    merge.mkdir()
    config = merge / ".config"
    env = kbuild_env()
    env["KCONFIG_CONFIG"] = str(config)

    result = subprocess.run(
        [
            str(kernel / "scripts/kconfig/merge_config.sh"),
            "-m",
            str(base_config),
            str(fragment),
        ],
        cwd=kernel,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    if result.returncode:
        return None, f"merge_config exited {result.returncode}"

    result = subprocess.run(
        [
            "make",
            "-s",
            "-C",
            str(kernel),
            f"O={merge}",
            "ARCH=arm64",
            "olddefconfig",
        ],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    if result.returncode or not config.is_file():
        return None, f"olddefconfig exited {result.returncode}"

    return config, ""


def main():
    parser = argparse.ArgumentParser(
        description="Resolve optional Extended Network Kconfig requests"
    )
    parser.add_argument("--kernel", required=True)
    parser.add_argument("--base-config", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--enabled", choices=("yes", "no"), required=True)
    args = parser.parse_args()

    kernel = Path(args.kernel).resolve()
    base_config = Path(args.base_config).resolve()
    profile = Path(args.profile).resolve()
    output = Path(args.output_dir).resolve()
    closure_tool = Path(__file__).resolve().parent / "kconfig-closure.py"

    for required in (kernel, base_config, profile, closure_tool):
        if not required.exists():
            raise SystemExit(f"Required Extended Network input missing: {required}")

    output.mkdir(parents=True, exist_ok=True)
    requests = read_requests(profile)
    available = scan_symbols(kernel)
    original = read_config(base_config)
    current_path = output / "working.config"
    shutil.copy2(base_config, current_path)
    entries = []

    for index, symbol in enumerate(requests, 1):
        base_value = original.get(symbol, "n")
        current = read_config(current_path)
        current_value = current.get(symbol, "n")
        entry = {
            "symbol": symbol,
            "requested": "m",
            "base_value": base_value,
            "final_value": current_value,
        }

        if base_value in ("y", "m"):
            entry["status"] = "already"
            entry["reason"] = "preserved stock/board value"
            entries.append(entry)
            continue

        if args.enabled == "no":
            entry["status"] = "disabled"
            entry["reason"] = "Extended Network not selected"
            entries.append(entry)
            continue

        if symbol not in available:
            entry["status"] = "skipped"
            entry["reason"] = "symbol unavailable in selected Linux tree"
            entries.append(entry)
            continue

        with tempfile.TemporaryDirectory(prefix=f"extended-{index:02d}-") as tmp:
            resolved, reason = resolve_one(
                kernel,
                closure_tool,
                current_path,
                symbol,
                Path(tmp),
            )

            if resolved is None:
                entry["status"] = "skipped"
                entry["reason"] = reason
                entries.append(entry)
                continue

            result_values = read_config(resolved)
            result_value = result_values.get(symbol, "n")
            entry["final_value"] = result_value

            if result_value != "m":
                entry["status"] = "skipped"
                entry["reason"] = (
                    f"requested module but Kconfig produced {result_value}"
                )
                entries.append(entry)
                continue

            shutil.copy2(resolved, current_path)
            entry["status"] = "enabled"
            entry["reason"] = "module request and dependencies resolved"
            entries.append(entry)

    final_config = output / "generated-final.config"
    shutil.copy2(current_path, final_config)
    current_path.unlink()
    final = read_config(final_config)

    delta = {
        symbol: value
        for symbol, value in final.items()
        if original.get(symbol, "n") != value
    }
    write_config(output / "extended-network.config", delta)

    counts = {
        state: sum(1 for entry in entries if entry["status"] == state)
        for state in ("enabled", "already", "skipped", "disabled")
    }

    payload = {
        "enabled": args.enabled == "yes",
        "profile": str(profile),
        "counts": counts,
        "entries": entries,
    }
    (output / "extended-network-report.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = [
        "Extended Network Kconfig Report",
        "===============================",
        "",
        f"Enabled: {args.enabled}",
        f"Requested: {len(entries)}",
        f"New modules enabled: {counts['enabled']}",
        f"Already in stock/board config: {counts['already']}",
        f"Skipped: {counts['skipped']}",
        "",
    ]

    for entry in entries:
        report.append(
            f"{entry['status'].upper():8} {entry['symbol']} "
            f"base={entry['base_value']} final={entry['final_value']} "
            f"- {entry['reason']}"
        )

    (output / "extended-network-report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print("Extended Network Kconfig")
    print("------------------------")
    print(f"Enabled:          {args.enabled}")
    print(f"New modules:      {counts['enabled']}")
    print(f"Already present:  {counts['already']}")
    print(f"Skipped:          {counts['skipped']}")
    print(f"Final config:     {final_config}")
    print(f"Report:           {output / 'extended-network-report.txt'}")


if __name__ == "__main__":
    main()
