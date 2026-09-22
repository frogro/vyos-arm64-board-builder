#!/usr/bin/env python3
"""Validate and consume an armbian-board-scanner catalog.

The scanner and the VyOS image builder deliberately remain separate projects.
This module is the compatibility boundary between them: it validates a complete
catalog in one pass and resolves the hardware reference for a VyOS kernel line.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import shlex
import sys
from typing import Any, Iterable


PRIORITY = ("current", "edge", "vendor")
RESOLVED_STATES = {"resolved", "excluded-architecture"}
KNOWN_PROVIDERS = {
    "armbian-uboot",
    "raspberrypi-native",
    "firmware-uefi",
    "qualcomm-abl",
    "external-or-native-firmware",
    "unknown",
}
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
KERNEL_LINE_RE = re.compile(r"^[0-9]+\.[0-9]+$")


@dataclass
class Finding:
    level: str
    code: str
    message: str
    board: str | None = None
    target: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "board": self.board,
            "target": self.target,
        }


@dataclass
class Audit:
    catalog_root: Path
    commit: str
    findings: list[Finding] = field(default_factory=list)
    profiles: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    index_entries: list[dict[str, Any]] = field(default_factory=list)
    inventory: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(
        self,
        level: str,
        code: str,
        message: str,
        board: str | None = None,
        target: str | None = None,
    ) -> None:
        self.findings.append(Finding(level, code, message, board, target))

    def error(
        self,
        code: str,
        message: str,
        board: str | None = None,
        target: str | None = None,
    ) -> None:
        self.add("FAIL", code, message, board, target)

    def warn(
        self,
        code: str,
        message: str,
        board: str | None = None,
        target: str | None = None,
    ) -> None:
        self.add("WARN", code, message, board, target)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def resolve_catalog_root(path: Path) -> tuple[Path, str]:
    """Accept either catalog/, catalog/<commit>/, or an archive extraction root."""

    path = path.resolve()
    candidates = (path, path / "catalog")
    for candidate in candidates:
        latest = candidate / "LATEST"
        if latest.is_file():
            commit = latest.read_text(encoding="utf-8").strip()
            root = candidate / commit
            if not root.is_dir():
                raise ValueError(f"LATEST points to a missing catalog: {root}")
            return root, commit

    if (path / "index.json").is_file():
        data = _read_json(path / "index.json")
        commit = data.get("armbian_commit")
        if not isinstance(commit, str):
            raise ValueError(f"index.json has no armbian_commit: {path}")
        return path, commit

    raise ValueError(f"not an armbian-board-scanner catalog: {path}")


def _safe_child(root: Path, relative: str) -> Path:
    child = (root / relative).resolve()
    if child != root and root not in child.parents:
        raise ValueError(f"catalog path escapes its root: {relative}")
    return child


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    lines = path.read_text(encoding="utf-8").splitlines()
    position = 0
    while position < len(lines):
        number = position + 1
        line = lines[position].strip()
        position += 1
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{number}: invalid environment assignment")
        name, encoded = line.split("=", 1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"{path}:{number}: invalid variable name {name!r}")
        # Some Armbian target maps are intentionally multiline shell strings.
        # Continue until POSIX quoting is complete, without evaluating the file.
        while True:
            try:
                tokens = shlex.split(encoded, posix=True)
                break
            except ValueError as error:
                if "No closing quotation" not in str(error) or position >= len(lines):
                    raise ValueError(f"{path}:{number}: {error}") from error
                encoded += "\n" + lines[position]
                position += 1
        if len(tokens) > 1:
            raise ValueError(f"{path}:{number}: assignment contains shell words")
        values[name] = tokens[0] if tokens else ""
    return values


def _require_string(
    audit: Audit,
    value: Any,
    field_name: str,
    board: str,
    target: str,
) -> str | None:
    if not isinstance(value, str) or not value:
        audit.error("missing-field", f"{field_name} must be a non-empty string", board, target)
        return None
    return value


def _validate_boot(audit: Audit, profile: dict[str, Any], board: str, target: str) -> None:
    boot = profile.get("boot")
    if not isinstance(boot, dict):
        audit.error("boot-contract", "boot must be an object", board, target)
        return

    provider = boot.get("provider")
    builds_uboot = boot.get("armbian_will_build_uboot")
    state = boot.get("uboot_metadata_state")
    handoff = boot.get("handoff")

    if provider not in KNOWN_PROVIDERS:
        audit.error("boot-provider", f"unknown boot provider: {provider!r}", board, target)

    if builds_uboot is True:
        if provider != "armbian-uboot":
            audit.error(
                "uboot-provider-mismatch",
                "ARMBIAN_WILL_BUILD_UBOOT=true requires provider=armbian-uboot",
                board,
                target,
            )
        if state != "active":
            audit.error("uboot-state", "built U-Boot metadata must be active", board, target)
        for name in ("config", "source", "branch"):
            _require_string(audit, boot.get(name), f"boot.{name}", board, target)
    elif builds_uboot is False:
        if provider == "armbian-uboot":
            audit.error(
                "uboot-provider-mismatch",
                "provider=armbian-uboot but Armbian will not build U-Boot",
                board,
                target,
            )
        if state == "active":
            audit.error("uboot-state", "inactive U-Boot cannot have active metadata", board, target)

    if provider == "raspberrypi-native":
        mode = handoff.get("armbian_mode") if isinstance(handoff, dict) else None
        compatibility = handoff.get("vyos_compatibility") if isinstance(handoff, dict) else None
        if builds_uboot is not False or state != "inactive-defaults":
            audit.error(
                "raspberrypi-uboot",
                "Raspberry Pi native boot must ignore inactive U-Boot defaults",
                board,
                target,
            )
        if mode != "config.txt-direct-kernel" or compatibility != "direct-kernel-sync-required":
            audit.error(
                "raspberrypi-handoff",
                "Raspberry Pi native boot requires config.txt direct-kernel handoff",
                board,
                target,
            )


def _validate_profile(
    audit: Audit,
    entry: dict[str, Any],
    profile: dict[str, Any],
    env_path: Path,
) -> None:
    board = str(entry.get("board") or "")
    target = str(entry.get("target") or "")
    identity = profile.get("identity")
    source = profile.get("source")
    scan = profile.get("scan")
    kernel = profile.get("kernel")
    device_tree = profile.get("device_tree")

    if profile.get("schema_version") != 1:
        audit.error("schema-version", "profile schema_version must be 1", board, target)
    if not isinstance(identity, dict):
        audit.error("identity-contract", "identity must be an object", board, target)
        return
    if not isinstance(source, dict) or source.get("armbian_commit") != audit.commit:
        audit.error("commit-mismatch", "profile Armbian commit differs from catalog", board, target)
    if not isinstance(scan, dict) or scan.get("status") != entry.get("status"):
        audit.error("status-mismatch", "index and profile scan status differ", board, target)
    if identity.get("board") != board or identity.get("target") != target:
        audit.error("identity-mismatch", "index and profile identity differ", board, target)
    if identity.get("architecture") != entry.get("architecture"):
        audit.error("architecture-mismatch", "index and profile architecture differ", board, target)
    if profile.get("boot", {}).get("provider") != entry.get("provider"):
        audit.error("provider-mismatch", "index and profile boot provider differ", board, target)

    targets = identity.get("kernel_targets")
    if not isinstance(targets, list) or target not in targets:
        audit.error("target-set", "selected target is absent from kernel_targets", board, target)

    if not isinstance(kernel, dict) or not KERNEL_LINE_RE.fullmatch(
        str(kernel.get("major_minor") or "")
    ):
        audit.error("kernel-line", "kernel.major_minor is invalid", board, target)

    if not isinstance(device_tree, dict):
        audit.error("dt-contract", "device_tree must be an object", board, target)
    else:
        mode = device_tree.get("mode")
        if mode == "single" and not device_tree.get("boot_fdt_file"):
            audit.error("dtb-missing", "single-DTB profile has no boot_fdt_file", board, target)
        if mode == "multi-model" and device_tree.get("boot_fdt_file"):
            audit.warn(
                "multi-model-dtb",
                "multi-model profile unexpectedly fixes one boot_fdt_file",
                board,
                target,
            )

    _validate_boot(audit, profile, board, target)

    if not env_path.is_file():
        audit.error("env-missing", f"portable profile environment missing: {env_path.name}", board, target)
        return
    try:
        env = _parse_env(env_path)
    except (OSError, ValueError) as error:
        audit.error("env-invalid", str(error), board, target)
        return

    if env.get("PROFILE_TARGET") != target:
        audit.error("env-target", "config.env PROFILE_TARGET differs from profile", board, target)
    env_targets = [item for item in env.get("AVAILABLE_KERNEL_TARGETS", "").split(",") if item]
    if env_targets != targets:
        audit.error("env-target-set", "config.env target list differs from profile", board, target)
    if env.get("KERNEL_MAJOR_MINOR") != kernel.get("major_minor"):
        audit.error("env-kernel-line", "config.env kernel line differs from profile", board, target)
    if env.get("ARMBIAN_WILL_BUILD_UBOOT") not in {"yes", "no"}:
        audit.error("env-uboot", "config.env has no boolean U-Boot decision", board, target)
    text = env_path.read_text(encoding="utf-8")
    if re.search(r"(^|[=:'\" ])/(home|root|mnt|workspace|tmp)/", text, re.MULTILINE):
        audit.error("env-host-path", "config.env contains a scanner-host path", board, target)


def audit_catalog(path: Path) -> Audit:
    root, commit = resolve_catalog_root(path)
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError(f"catalog does not use a full Armbian commit: {commit!r}")

    audit = Audit(root, commit)
    index_path = root / "index.json"
    inventory_path = root / "inventory.json"
    if not index_path.is_file() or not inventory_path.is_file():
        raise ValueError("catalog requires index.json and inventory.json")

    index = _read_json(index_path)
    inventory_data = _read_json(inventory_path)
    if index.get("armbian_commit") != commit or inventory_data.get("armbian_commit") != commit:
        audit.error("root-commit", "root, index and inventory commits differ")

    entries = index.get("entries")
    boards = inventory_data.get("boards")
    if not isinstance(entries, list) or not isinstance(boards, list):
        raise ValueError("catalog index.entries and inventory.boards must be arrays")
    audit.index_entries = entries

    for item in boards:
        board = item.get("board") if isinstance(item, dict) else None
        if not isinstance(board, str) or not board:
            audit.error("inventory-board", "inventory entry has no board identifier")
            continue
        if board in audit.inventory:
            audit.error("inventory-duplicate", "duplicate inventory board", board)
        audit.inventory[board] = item

    seen: set[tuple[str, str]] = set()
    observed_counts: Counter[str] = Counter()
    for entry in entries:
        if not isinstance(entry, dict):
            audit.error("index-entry", "index entry must be an object")
            continue
        state = entry.get("status")
        observed_counts[str(state)] += 1
        if state == "manual-review-required":
            relative = entry.get("profile")
            if not isinstance(relative, str):
                audit.error("manual-profile", "manual entry has no profile path")
                continue
            try:
                profile_path = _safe_child(root, relative)
                profile = _read_json(profile_path)
            except (OSError, ValueError, json.JSONDecodeError) as error:
                audit.error("manual-profile", str(error))
                continue
            if profile.get("scan", {}).get("status") != state:
                audit.error("manual-status", "manual index/profile status mismatch")
            continue
        if state not in RESOLVED_STATES:
            # Scanner failures and inventory skips intentionally have no stable profile.
            continue

        board = entry.get("board")
        target = entry.get("target")
        relative = entry.get("profile")
        if not all(isinstance(value, str) and value for value in (board, target, relative)):
            audit.error("index-identity", "resolved index entry is incomplete")
            continue
        key = (board, target)
        if key in seen:
            audit.error("index-duplicate", "duplicate board/target entry", board, target)
            continue
        seen.add(key)
        try:
            profile_path = _safe_child(root, relative)
            profile = _read_json(profile_path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            audit.error("profile-read", str(error), board, target)
            continue
        audit.profiles[key] = profile
        _validate_profile(audit, entry, profile, profile_path.with_name("config.env"))

    declared_counts = index.get("counts")
    if isinstance(declared_counts, dict):
        normalized = {str(k): int(v) for k, v in declared_counts.items()}
        if normalized != dict(observed_counts):
            audit.error(
                "index-counts",
                f"declared counts {normalized} differ from observed {dict(observed_counts)}",
            )

    expected: set[tuple[str, str]] = set()
    for board, item in audit.inventory.items():
        targets = item.get("targets")
        if isinstance(targets, list):
            expected.update((board, target) for target in targets if isinstance(target, str))
    missing = sorted(expected - seen)
    for board, target in missing:
        matching = [
            item
            for item in entries
            if isinstance(item, dict)
            and item.get("board") == board
            and item.get("target") == target
        ]
        if not matching:
            audit.error("target-coverage", "inventory target has no index entry", board, target)

    # All targets of one board must describe the same board source and identity.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (board, _), profile in audit.profiles.items():
        grouped[board].append(profile)
    for board, profiles in grouped.items():
        # LINUXFAMILY and sometimes BOARDFAMILY legitimately change with a
        # vendor/current/edge target. Stable physical identity must not.
        identity_fields = ("name", "vendor", "architecture")
        for name in identity_fields:
            values = {profile.get("identity", {}).get(name) for profile in profiles}
            if len(values) > 1:
                audit.error("cross-target-identity", f"identity.{name} differs across targets", board)
        hashes = {profile.get("source", {}).get("board_file_sha256") for profile in profiles}
        if len(hashes) > 1:
            audit.error("cross-target-source", "board source hash differs across targets", board)

    return audit


def kernel_line(version: str) -> str:
    match = re.match(r"^([0-9]+\.[0-9]+)(?:\.|$)", version.strip())
    if not match:
        raise ValueError(f"invalid kernel version: {version!r}")
    return match.group(1)


def select_reference(
    profiles: Iterable[dict[str, Any]],
    version: str,
    override: str = "auto",
) -> dict[str, Any] | None:
    candidates = list(profiles)
    if override != "auto":
        return next(
            (item for item in candidates if item.get("identity", {}).get("target") == override),
            None,
        )

    wanted = kernel_line(version)
    exact = [item for item in candidates if item.get("kernel", {}).get("major_minor") == wanted]
    order = {name: position for position, name in enumerate(PRIORITY)}
    exact.sort(
        key=lambda item: (
            order.get(item.get("identity", {}).get("target"), len(PRIORITY)),
            item.get("identity", {}).get("kernel_targets", []).index(
                item.get("identity", {}).get("target")
            ),
        )
    )
    return exact[0] if exact else None


def load_models(path: Path | None, audit: Audit) -> list[dict[str, Any]]:
    if path is None:
        return []
    models: list[dict[str, Any]] = []
    for model_path in sorted(path.glob("*.json")):
        try:
            model = _read_json(model_path)
        except (OSError, json.JSONDecodeError) as error:
            audit.error("model-read", f"{model_path}: {error}")
            continue
        model_id = model.get("model")
        board = model.get("armbian_board")
        if model.get("schema_version") != 1 or not isinstance(model_id, str):
            audit.error("model-schema", f"invalid model profile: {model_path}")
            continue
        if not isinstance(board, str) or board not in audit.inventory:
            audit.error("model-board", f"model {model_id} references unknown board {board!r}")
            continue
        available = [profile for (name, _), profile in audit.profiles.items() if name == board]
        expected_provider = model.get("boot", {}).get("provider")
        providers = {profile.get("boot", {}).get("provider") for profile in available}
        if expected_provider not in providers:
            audit.error(
                "model-provider",
                f"model {model_id} expects {expected_provider!r}, catalog has {sorted(providers)!r}",
                board,
            )
        dtb = model.get("device_tree", {}).get("boot_fdt_file")
        if not isinstance(dtb, str) or not dtb.endswith(".dtb") or dtb.startswith("/"):
            audit.error("model-dtb", f"model {model_id} has invalid DTB path", board)
        models.append(model)
    return models


def build_report(
    audit: Audit,
    models: list[dict[str, Any]],
    vyos_kernel: str | None,
) -> dict[str, Any]:
    levels = Counter(item.level for item in audit.findings)
    providers = Counter(
        profile.get("boot", {}).get("provider") for profile in audit.profiles.values()
    )
    selections: list[dict[str, Any]] = []
    if vyos_kernel:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for (board, _), profile in audit.profiles.items():
            if profile.get("identity", {}).get("architecture") == "arm64":
                grouped[board].append(profile)
        for board in sorted(grouped):
            selected = select_reference(grouped[board], vyos_kernel)
            selections.append(
                {
                    "board": board,
                    "status": "exact-match" if selected else "no-exact-kernel-line",
                    "target": selected.get("identity", {}).get("target") if selected else None,
                    "kernel_major_minor": (
                        selected.get("kernel", {}).get("major_minor") if selected else None
                    ),
                }
            )

    return {
        "schema_version": 1,
        "catalog": str(audit.catalog_root),
        "armbian_commit": audit.commit,
        "profiles_checked": len(audit.profiles),
        "boards_checked": len({board for board, _ in audit.profiles}),
        "models_checked": len(models),
        "findings": dict(levels),
        "provider_counts": dict(sorted(providers.items(), key=lambda item: str(item[0]))),
        "vyos_kernel": vyos_kernel,
        "auto_reference_summary": dict(
            Counter(item["status"] for item in selections)
        ),
        "auto_references": selections,
        "details": [item.as_dict() for item in audit.findings],
    }


def resolve_requested_reference(
    audit: Audit,
    models: list[dict[str, Any]],
    requested: str,
    vyos_kernel: str,
    override: str = "auto",
) -> dict[str, Any]:
    model = next((item for item in models if item.get("model") == requested), None)
    board = model.get("armbian_board") if model else requested
    candidates = [
        profile
        for (profile_board, _), profile in audit.profiles.items()
        if profile_board == board
        and profile.get("scan", {}).get("status") == "resolved"
        and profile.get("identity", {}).get("architecture") == "arm64"
    ]
    if not candidates:
        raise ValueError(f"no resolved ARM64 profiles for {requested!r} (BOARD={board!r})")
    selected = select_reference(candidates, vyos_kernel, override=override)
    if selected is None:
        available = ", ".join(
            f"{item.get('identity', {}).get('target')}="
            f"{item.get('kernel', {}).get('major_minor')}"
            for item in candidates
        )
        if override == "auto":
            raise ValueError(
                f"no exact hardware reference for {requested!r} and VyOS "
                f"{kernel_line(vyos_kernel)}; available: {available}"
            )
        raise ValueError(
            f"developer override {override!r} is not offered by {board!r}; "
            f"available: {available}"
        )
    identity = selected.get("identity", {})
    device_tree = selected.get("device_tree", {})
    boot = selected.get("boot", {})
    model_dtb = model.get("device_tree", {}).get("boot_fdt_file") if model else None
    return {
        "schema_version": 1,
        "requested_board": requested,
        "model": model.get("model") if model else None,
        "armbian_board": board,
        "name": model.get("name") if model else identity.get("name"),
        "architecture": identity.get("architecture"),
        "soc": model.get("soc") if model else boot.get("soc"),
        "target": identity.get("target"),
        "selection_mode": "developer-override" if override != "auto" else "auto-exact",
        "vyos_kernel": vyos_kernel,
        "vyos_kernel_major_minor": kernel_line(vyos_kernel),
        "reference_kernel_major_minor": selected.get("kernel", {}).get("major_minor"),
        "boot_provider": model.get("boot", {}).get("provider") if model else boot.get("provider"),
        "boot_fdt_file": model_dtb or device_tree.get("boot_fdt_file"),
        "armbian_commit": audit.commit,
        "catalog_profile": selected,
        "model_profile": model,
    }


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate every Board x KERNEL_TARGET profile in a scanner catalog"
    )
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--vyos-kernel", help="calculate AUTO references for this kernel")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--strict-warnings", action="store_true")
    parser.add_argument("--select", metavar="BOARD_OR_MODEL")
    parser.add_argument(
        "--hardware-reference",
        default="auto",
        help="developer override; normal builds use auto",
    )
    parser.add_argument("--selection-output", type=Path)
    args = parser.parse_args(argv)

    try:
        audit = audit_catalog(args.catalog)
        models = load_models(args.models_dir, audit)
        report = build_report(audit, models, args.vyos_kernel)
        selection = None
        if args.select:
            if not args.vyos_kernel:
                raise ValueError("--select requires --vyos-kernel")
            selection = resolve_requested_reference(
                audit,
                models,
                args.select,
                args.vyos_kernel,
                args.hardware_reference,
            )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2

    if args.report:
        _write_json(args.report, report)
    if args.selection_output:
        if selection is None:
            print("FAIL: --selection-output requires --select", file=sys.stderr)
            return 2
        _write_json(args.selection_output, selection)

    failures = report["findings"].get("FAIL", 0)
    warnings = report["findings"].get("WARN", 0)
    auto = report.get("auto_reference_summary", {})
    print(f"Catalog commit: {audit.commit}")
    print(f"Profiles:       {report['profiles_checked']}")
    print(f"Boards:         {report['boards_checked']}")
    print(f"Models:         {report['models_checked']}")
    print(f"PASS:           {report['profiles_checked'] - failures}")
    print(f"WARN:           {warnings}")
    print(f"FAIL:           {failures}")
    if args.vyos_kernel:
        print(
            "AUTO exact:     "
            f"{auto.get('exact-match', 0)} / {len(report['auto_references'])} ARM64 boards"
        )
    if selection is not None:
        print(
            "Selected:       "
            f"{selection['requested_board']} -> {selection['armbian_board']}/"
            f"{selection['target']} ({selection['reference_kernel_major_minor']})"
        )
    for finding in audit.findings:
        location = "/".join(item for item in (finding.board, finding.target) if item)
        prefix = f" [{location}]" if location else ""
        print(f"{finding.level}{prefix} {finding.code}: {finding.message}")

    if failures or (args.strict_warnings and warnings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
