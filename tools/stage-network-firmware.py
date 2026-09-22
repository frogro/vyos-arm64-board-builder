#!/usr/bin/env python3

"""Stage network firmware from the linux-firmware revision pinned by VyOS."""

import argparse
import glob
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path, PurePosixPath


def read_lines(path):
    result = []

    with Path(path).open(encoding="utf-8") as stream:
        for raw in stream:
            line = raw.strip()

            if line and not line.startswith("#"):
                result.append(line)

    return result


def read_catalog(path):
    entries = []
    seen = set()

    with Path(path).open(encoding="utf-8") as stream:
        for lineno, raw in enumerate(stream, 1):
            line = raw.rstrip("\n")

            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")

            if len(parts) != 4:
                raise SystemExit(
                    f"Invalid module catalog row at {path}:{lineno}"
                )

            category, symbol, module, family = parts
            key = (symbol, module)

            if key in seen:
                raise SystemExit(f"Duplicate module catalog entry: {key}")

            seen.add(key)
            entries.append(
                {
                    "category": category,
                    "symbol": symbol,
                    "module": module,
                    "family": family,
                }
            )

    return entries


def read_supplements(path):
    result = []

    with Path(path).open(encoding="utf-8") as stream:
        for lineno, raw in enumerate(stream, 1):
            line = raw.rstrip("\n")

            if not line or line.startswith("#"):
                continue

            parts = line.split("\t")

            if len(parts) != 2:
                raise SystemExit(
                    f"Invalid firmware supplement at {path}:{lineno}"
                )

            result.append(tuple(parts))

    return result


def linux_firmware_pin(vyos_tree):
    package_file = (
        Path(vyos_tree)
        / "scripts/package-build/linux-kernel/package.toml"
    )

    with package_file.open("rb") as stream:
        data = tomllib.load(stream)

    for package in data.get("packages", []):
        if package.get("name") == "linux-firmware":
            url = str(package.get("scm_url", "")).strip()
            revision = str(package.get("commit_id", "")).strip()

            if not url or not revision:
                raise RuntimeError(
                    f"Incomplete linux-firmware pin in {package_file}"
                )

            return url, revision, package_file

    raise RuntimeError(f"linux-firmware package missing from {package_file}")


def run(command, **kwargs):
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
        **kwargs,
    ).stdout.strip()


def prepare_source(cache_dir, url, revision):
    cache_dir = Path(cache_dir)
    stamp = cache_dir / ".vyos-linux-firmware-pin.json"

    if (cache_dir / ".git").is_dir() and stamp.is_file():
        try:
            saved = json.loads(stamp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            saved = {}

        if saved.get("url") == url and saved.get("revision") == revision:
            commit = run(["git", "-C", str(cache_dir), "rev-parse", "HEAD"])
            return cache_dir, commit

    if cache_dir.exists():
        shutil.rmtree(cache_dir)

    cache_dir.mkdir(parents=True)
    run(["git", "-C", str(cache_dir), "init", "--quiet"])
    run(["git", "-C", str(cache_dir), "remote", "add", "origin", url])
    run(
        [
            "git",
            "-C",
            str(cache_dir),
            "fetch",
            "--depth=1",
            "origin",
            revision,
        ]
    )
    run(
        [
            "git",
            "-C",
            str(cache_dir),
            "checkout",
            "--quiet",
            "--detach",
            "FETCH_HEAD",
        ]
    )
    commit = run(["git", "-C", str(cache_dir), "rev-parse", "HEAD"])
    stamp.write_text(
        json.dumps(
            {"url": url, "revision": revision, "commit": commit},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return cache_dir, commit


def modinfo(modules_root, kernel_release, module, field):
    command = [
        "modinfo",
        "-b",
        str(modules_root),
        "-k",
        kernel_release,
        "-F",
        field,
        module,
    ]

    try:
        value = run(command)
    except subprocess.CalledProcessError:
        return None

    return [line.strip() for line in value.splitlines() if line.strip()]


def module_closure(modules_root, kernel_release, roots, group):
    pending = list(sorted(roots))
    modules = set()
    status = []

    while pending:
        module = pending.pop(0)

        if module in modules:
            continue

        modules.add(module)
        filenames = modinfo(
            modules_root, kernel_release, module, "filename"
        )

        if not filenames:
            status.append(
                {"group": group, "module": module, "status": "missing"}
            )
            continue

        status.append(
            {
                "group": group,
                "module": module,
                "status": "present",
                "filename": filenames[0],
            }
        )
        depends = modinfo(
            modules_root, kernel_release, module, "depends"
        ) or []

        for line in depends:
            for dependency in line.split(","):
                dependency = dependency.strip()

                if dependency and dependency not in modules:
                    pending.append(dependency)

    return modules, status


def valid_firmware_pattern(pattern):
    path = PurePosixPath(pattern)
    return bool(pattern) and not path.is_absolute() and ".." not in path.parts


def copy_pattern(source, destination, pattern):
    if not valid_firmware_pattern(pattern):
        return []

    matches = sorted(glob.glob(str(source / pattern)))
    copied = []

    for name in matches:
        path = Path(name)

        if not path.is_file():
            continue

        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)

        # Install real bytes rather than a symlink whose target may not be
        # part of the selected closure.
        shutil.copy2(path.resolve(), target)
        copied.append(relative.as_posix())

    return copied


def main():
    parser = argparse.ArgumentParser(
        description="Stage VyOS-pinned firmware for network modules"
    )
    parser.add_argument("--vyos-tree", required=True)
    parser.add_argument("--modules-root", required=True)
    parser.add_argument("--kernel-release", required=True)
    parser.add_argument("--resolver-report", required=True)
    parser.add_argument("--module-catalog", required=True)
    parser.add_argument("--baseline-modules", required=True)
    parser.add_argument("--supplements", required=True)
    parser.add_argument("--cache-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()

    if output.exists():
        shutil.rmtree(output)

    firmware_root = output / "root/usr/lib/firmware"
    firmware_root.mkdir(parents=True)

    resolver_path = Path(args.resolver_report)
    resolver = json.loads(resolver_path.read_text(encoding="utf-8"))
    resolver_entries = {
        entry["symbol"]: entry for entry in resolver.get("entries", [])
    }
    catalog = read_catalog(args.module_catalog)
    baseline_roots = set(read_lines(args.baseline_modules))
    extended_roots = set()

    for entry in catalog:
        state = resolver_entries.get(entry["symbol"], {})

        # Catalog drivers which stock VyOS already provides still belong to
        # the optional broad firmware set. With Extended Network disabled,
        # only explicitly relevant baseline modules are staged.
        if resolver.get("enabled") and (
            state.get("base_value") in ("y", "m")
            or state.get("status") == "enabled"
        ):
            extended_roots.add(entry["module"])

    # Explicit baseline roots always win if a future catalog entry overlaps.
    extended_roots -= baseline_roots

    baseline, baseline_status = module_closure(
        args.modules_root,
        args.kernel_release,
        baseline_roots,
        "baseline",
    )
    extended, extended_status = module_closure(
        args.modules_root,
        args.kernel_release,
        extended_roots,
        "extended",
    )

    # Dependencies shared with a baseline module are baseline firmware.
    extended -= baseline
    module_status = baseline_status + [
        item for item in extended_status if item["module"] in extended
    ]
    requirements = {"baseline": [], "extended": []}

    for group, modules in (("baseline", baseline), ("extended", extended)):
        for module in sorted(modules):
            if not modinfo(
                args.modules_root, args.kernel_release, module, "filename"
            ):
                continue

            firmware = modinfo(
                args.modules_root, args.kernel_release, module, "firmware"
            ) or []

            for pattern in sorted(set(firmware)):
                requirements[group].append((module, pattern, "modinfo"))

    selected_modules = baseline | extended

    for module, pattern in read_supplements(args.supplements):
        if module not in selected_modules:
            continue

        group = "baseline" if module in baseline else "extended"
        requirements[group].append((module, pattern, "supplement"))

    source = None
    source_error = ""
    source_url = ""
    source_revision = ""
    source_commit = ""
    package_file = ""

    try:
        source_url, source_revision, package_path = linux_firmware_pin(
            args.vyos_tree
        )
        package_file = str(package_path)
        source, source_commit = prepare_source(
            args.cache_dir, source_url, source_revision
        )
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        source_error = str(error)

    installed = []
    missing = []

    for group in ("baseline", "extended"):
        unique = sorted(set(requirements[group]))
        requirements[group] = unique

        for module, pattern, origin in unique:
            copied = []

            if source is not None:
                copied = copy_pattern(source, firmware_root, pattern)

            if copied:
                for path in copied:
                    installed.append(
                        {
                            "group": group,
                            "module": module,
                            "pattern": pattern,
                            "path": path,
                            "origin": origin,
                        }
                    )
            else:
                missing.append(
                    {
                        "group": group,
                        "module": module,
                        "pattern": pattern,
                        "origin": origin,
                    }
                )

    for group in ("baseline", "extended"):
        path = output / f"required-firmware-{group}.txt"
        path.write_text(
            "".join(
                f"{module}\t{pattern}\t{origin}\n"
                for module, pattern, origin in requirements[group]
            ),
            encoding="utf-8",
        )

    (output / "required-firmware.txt").write_text(
        "".join(
            f"{item['group']}\t{item['module']}\t{item['pattern']}\t"
            f"{item['origin']}\n"
            for item in sorted(
                [
                    {
                        "group": group,
                        "module": module,
                        "pattern": pattern,
                        "origin": origin,
                    }
                    for group in ("baseline", "extended")
                    for module, pattern, origin in requirements[group]
                ],
                key=lambda item: (
                    item["group"], item["module"], item["pattern"]
                ),
            )
        ),
        encoding="utf-8",
    )

    (output / "installed-firmware.txt").write_text(
        "".join(
            f"{item['group']}\t{item['module']}\t{item['path']}\n"
            for item in sorted(
                installed,
                key=lambda item: (
                    item["group"], item["module"], item["path"]
                ),
            )
        ),
        encoding="utf-8",
    )
    (output / "missing-firmware.txt").write_text(
        "".join(
            f"{item['group']}\t{item['module']}\t{item['pattern']}\n"
            for item in missing
        ),
        encoding="utf-8",
    )

    shutil.copy2(
        resolver_path, output / "extended-network-kconfig-report.json"
    )
    text_report = resolver_path.with_suffix(".txt")

    if text_report.is_file():
        shutil.copy2(
            text_report, output / "extended-network-kconfig-report.txt"
        )

    manifest = {
        "kernel_release": args.kernel_release,
        "extended_network": bool(resolver.get("enabled")),
        "baseline_module_roots": sorted(baseline_roots),
        "extended_module_roots": sorted(extended_roots),
        "baseline_modules": sorted(baseline),
        "extended_modules": sorted(extended),
        "module_status": module_status,
        "linux_firmware": {
            "package_file": package_file,
            "url": source_url,
            "revision": source_revision,
            "resolved_commit": source_commit,
            "error": source_error,
        },
        "installed": installed,
        "missing": missing,
    }
    (output / "network-firmware-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    report = [
        "Network Firmware Report",
        "=======================",
        "",
        f"Kernel: {args.kernel_release}",
        f"Extended Network: {'yes' if resolver.get('enabled') else 'no'}",
        f"VyOS linux-firmware revision: {source_revision or 'unavailable'}",
        f"Resolved linux-firmware commit: {source_commit or 'unavailable'}",
        f"Baseline modules: {len(baseline)}",
        f"Extended modules: {len(extended)}",
        f"Firmware files installed: {len(installed)}",
        f"Firmware requirements missing: {len(missing)}",
    ]

    if source_error:
        report.extend(["", f"SOURCE WARNING: {source_error}"])

    missing_modules = [
        item for item in module_status if item["status"] == "missing"
    ]

    if missing_modules:
        report.extend(["", "Modules not present (warning):"])
        report.extend(
            f"  {item['group']}: {item['module']}" for item in missing_modules
        )

    if missing:
        report.extend(["", "Firmware not found (warning):"])
        report.extend(
            f"  {item['group']}: {item['module']} -> {item['pattern']}"
            for item in missing
        )

    (output / "extended-network-report.txt").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )

    print("Network firmware staging")
    print("------------------------")
    print(f"Extended Network:  {'yes' if resolver.get('enabled') else 'no'}")
    print(f"Baseline modules:  {len(baseline)}")
    print(f"Extended modules:  {len(extended)}")
    print(f"Firmware installed: {len(installed)}")
    print(f"Firmware missing:   {len(missing)} (warning only)")
    print(f"Output:             {output}")


if __name__ == "__main__":
    main()
