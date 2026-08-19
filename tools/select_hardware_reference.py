#!/usr/bin/env python3
"""Select an Armbian hardware reference from the real VyOS kernel line.

Normal users never choose current/vendor/edge.  The selected target must match
the VyOS kernel major.minor exactly.  ``--hardware-reference`` is the explicit
developer escape hatch and is recorded as such in the output manifest.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from board_catalog import PRIORITY, kernel_line  # noqa: E402


ASSIGNMENT_RE = re.compile(
    r"^\s*(?:export\s+)?(?:declare\s+(?:(?:-[A-Za-z]+)\s+)*)?"
    r"(?P<name>[A-Z][A-Z0-9_]*)\s*=\s*"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^#\n]*)",
    re.MULTILINE,
)


def parse_simple_assignments(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for match in ASSIGNMENT_RE.finditer(text):
        raw = match.group("value").strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1]
        values.setdefault(match.group("name"), []).append(raw)
    return values


def discover_targets(board_file: Path) -> list[str]:
    assignments = parse_simple_assignments(board_file.read_text(encoding="utf-8"))
    targets: list[str] = []
    for raw in assignments.get("KERNEL_TARGET", []):
        if "$" in raw or "`" in raw:
            continue
        for item in raw.split(","):
            target = item.strip()
            if target and target not in targets:
                targets.append(target)
    if not targets:
        raise ValueError(f"KERNEL_TARGET is not statically discoverable: {board_file}")
    return targets


def load_models(path: Path) -> list[dict[str, Any]]:
    result = []
    if not path.is_dir():
        return result
    for model_path in sorted(path.glob("*.json")):
        model = json.loads(model_path.read_text(encoding="utf-8"))
        if model.get("schema_version") != 1:
            raise ValueError(f"unsupported model profile: {model_path}")
        model["_path"] = str(model_path)
        result.append(model)
    return result


def find_board_file(armbian: Path, board: str) -> Path:
    matches = sorted((armbian / "config" / "boards").glob(f"{board}.*"))
    matches = [item for item in matches if item.suffix in {".conf", ".csc", ".tvb", ".eos"}]
    if len(matches) != 1:
        raise ValueError(f"expected one Armbian definition for {board!r}, found {len(matches)}")
    return matches[0]


def read_shell_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: invalid environment assignment")
        name, encoded = line.split("=", 1)
        words = shlex.split(encoded)
        if len(words) > 1:
            raise ValueError(f"{path}:{number}: assignment has multiple words")
        values[name] = words[0] if words else ""
    return values


def resolve_targets(
    root: Path,
    armbian: Path,
    board: str,
    targets: list[str],
    work: Path,
) -> list[dict[str, str]]:
    resolver = root / "tools" / "resolve-armbian-effective-config.sh"
    resolver_env = os.environ.copy()
    resolver_env["ARMBIAN"] = str(armbian.resolve())
    result: list[dict[str, str]] = []
    for target in targets:
        destination = work / target
        process = subprocess.run(
            [str(resolver), board, target, str(destination)],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=resolver_env,
        )
        if process.returncode:
            raise ValueError(
                f"effective Armbian resolution failed for {board}/{target}:\n{process.stdout}"
            )
        env = read_shell_env(destination / "config.env")
        line = env.get("KERNEL_MAJOR_MINOR", "")
        if not re.fullmatch(r"[0-9]+\.[0-9]+", line):
            branch = env.get("KERNELBRANCH", "")
            match = re.search(r"(?<![0-9])([0-9]+\.[0-9]+)(?![0-9])", branch)
            line = match.group(1) if match else ""
        result.append(
            {
                "target": target,
                "kernel_major_minor": line,
                "linux_family": env.get("LINUXFAMILY", env.get("BOARDFAMILY", "")),
                "kernel_config": env.get("LINUXCONFIG", ""),
            }
        )
    return result


def choose(candidates: list[dict[str, str]], version: str, override: str) -> dict[str, str]:
    if override != "auto":
        for item in candidates:
            if item["target"] == override:
                return item
        raise ValueError(f"developer override {override!r} is not offered")
    wanted = kernel_line(version)
    exact = [item for item in candidates if item["kernel_major_minor"] == wanted]
    priority = {name: position for position, name in enumerate(PRIORITY)}
    exact.sort(key=lambda item: priority.get(item["target"], len(PRIORITY)))
    if not exact:
        available = ", ".join(
            f"{item['target']}={item['kernel_major_minor'] or 'unknown'}" for item in candidates
        )
        raise ValueError(f"no exact Armbian reference for VyOS {wanted}; available: {available}")
    return exact[0]


def shell_quote(value: Any) -> str:
    if value is None:
        value = ""
    if isinstance(value, bool):
        value = "yes" if value else "no"
    return shlex.quote(str(value))


def write_env(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(f"{name}={shell_quote(value)}\n" for name, value in data.items()),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--armbian", type=Path, required=True)
    parser.add_argument("--board", required=True)
    parser.add_argument("--vyos-kernel", required=True)
    parser.add_argument("--hardware-reference", default="auto")
    parser.add_argument("--models-dir", type=Path, default=ROOT / "profiles" / "board-models")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        models = load_models(args.models_dir)
        model = next((item for item in models if item.get("model") == args.board), None)
        armbian_board = model.get("armbian_board") if model else args.board
        board_file = find_board_file(args.armbian, armbian_board)
        targets = discover_targets(board_file)
        with tempfile.TemporaryDirectory(prefix="vyos-hw-reference-") as temporary:
            candidates = resolve_targets(
                args.root.resolve(), args.armbian, armbian_board, targets, Path(temporary)
            )
        selected = choose(candidates, args.vyos_kernel, args.hardware_reference)
        device_tree = model.get("device_tree", {}) if model else {}
        boot = model.get("boot", {}) if model else {}
        output = {
            "REQUESTED_BOARD": args.board,
            "ARMBIAN_BOARD": armbian_board,
            "BOARD_MODEL": model.get("model") if model else "",
            "BOARD_NAME_OVERRIDE": model.get("name") if model else "",
            "BOARD_SOC_OVERRIDE": model.get("soc") if model else "",
            "BOOT_FDT_FILE_OVERRIDE": device_tree.get("boot_fdt_file", ""),
            "FIRMWARE_PROVIDER_OVERRIDE": boot.get("provider", ""),
            "HW_BRANCH": selected["target"],
            "HW_SELECTION_MODE": (
                "developer-override" if args.hardware_reference != "auto" else "auto-exact"
            ),
            "VYOS_KERNEL_VERSION": args.vyos_kernel,
            "VYOS_KERNEL_MAJOR_MINOR": kernel_line(args.vyos_kernel),
            "REFERENCE_KERNEL_MAJOR_MINOR": selected["kernel_major_minor"],
            "AVAILABLE_KERNEL_TARGETS": ",".join(targets),
            "BOARD_MODEL_PROFILE": (
                str(Path(model["_path"]).resolve().relative_to(args.root.resolve()))
                if model
                else ""
            ),
        }
        write_env(args.output, output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Requested board: {args.board}")
    print(f"Armbian BOARD:   {armbian_board}")
    print(f"VyOS kernel:     {args.vyos_kernel}")
    print(f"HW reference:    {selected['target']} ({selected['kernel_major_minor']})")
    print(f"Selection mode:  {output['HW_SELECTION_MODE']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
