#!/usr/bin/env python3
"""Resolve an opt-in, exact-board KVM hardware provider."""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "disabled"}
TOKEN = re.compile(r"[a-z0-9]+(?:[+._-][a-z0-9]+)*")
BOARD = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*|\*")


def parse_enabled(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"invalid enabled value: {value}")


def read_registry(path: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 6:
            raise ValueError(f"{path}:{number}: expected six pipe-separated fields")
        board, provider, config, ready, backend, hid = parts
        if not BOARD.fullmatch(board):
            raise ValueError(f"{path}:{number}: invalid board: {board}")
        if board in seen:
            raise ValueError(f"{path}:{number}: duplicate board: {board}")
        if not TOKEN.fullmatch(provider) or not TOKEN.fullmatch(backend):
            raise ValueError(f"{path}:{number}: invalid provider/backend token")
        if hid not in {"yes", "no", "runtime"}:
            raise ValueError(f"{path}:{number}: invalid HID capability: {hid}")
        seen.add(board)
        entries.append({
            "board": board,
            "provider": provider,
            "kernel_config": config,
            "ready_config": ready,
            "capture_backend": backend,
            "hid_gadget": hid,
        })
    return entries


def select(entries: list[dict[str, str]], board: str, enabled: bool) -> dict[str, str]:
    if not enabled:
        return {
            "board": board,
            "provider": "disabled",
            "kernel_config": "",
            "ready_config": "",
            "capture_backend": "disabled",
            "hid_gadget": "no",
            "selection": "disabled",
        }
    exact = next((entry for entry in entries if entry["board"] == board), None)
    fallback = next((entry for entry in entries if entry["board"] == "*"), None)
    chosen = exact or fallback
    if chosen is None:
        raise ValueError(f"no KVM hardware provider for board: {board}")
    result = dict(chosen)
    result["board"] = board
    result["selection"] = "exact" if exact else "generic"
    return result


def validate_paths(root: Path, result: dict[str, str]) -> None:
    root = root.resolve()
    for field in ("kernel_config", "ready_config"):
        relative = result[field]
        if not relative:
            continue
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ValueError(f"{field} escapes repository root: {relative}") from error
        if not candidate.is_file():
            raise ValueError(f"{field} not found: {relative}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", required=True)
    parser.add_argument("--enabled", default="no")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-env", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    try:
        enabled = parse_enabled(args.enabled)
        result = select(read_registry(args.registry), args.board, enabled)
        validate_paths(args.root, result)
    except ValueError as error:
        parser.error(str(error))

    data = {
        "schema": 1,
        "enabled": enabled,
        **result,
    }
    env = {
        "KVM_HARDWARE_PROVIDER": result["provider"],
        "KVM_HARDWARE_CONFIG": result["kernel_config"],
        "KVM_HARDWARE_READY_CONFIG": result["ready_config"],
        "KVM_CAPTURE_BACKEND": result["capture_backend"],
        "KVM_HID_GADGET": result["hid_gadget"],
        "KVM_HARDWARE_SELECTION": result["selection"],
    }
    args.output_env.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_env.write_text(
        "".join(f"{key}={shlex.quote(value)}\n" for key, value in env.items()),
        encoding="utf-8",
    )
    args.output_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
