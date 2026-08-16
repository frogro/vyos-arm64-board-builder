#!/usr/bin/env python3

import argparse
import configparser
import re
import subprocess
import tempfile
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


def read_boot_profile(path):
    parser = configparser.ConfigParser()
    parser.read(path)

    result = {}

    for section in parser.sections():
        raw_classes = parser[section].get(
            "required_classes", ""
        )

        raw_endpoints = parser[section].get(
            "endpoint_symbols", ""
        )

        result[section] = {
            "required_classes": [
                x.strip()
                for x in raw_classes.split(",")
                if x.strip()
            ],
            "endpoint_symbols": [
                x.strip()
                for x in raw_endpoints.split(",")
                if x.strip()
            ],
        }

    return result


def read_policy(path):
    result = {}

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            result[key.strip()] = value.strip()

    return result


def classify_symbol(symbol):
    s = symbol.upper()

    classes = set()

    if any(x in s for x in [
        "MMC",
        "SDHCI",
        "DWCMSHC",
    ]):
        classes.add("mmc")

    if any(x in s for x in [
        "PCIE",
        "PCI_",
    ]):
        classes.add("pci")
        classes.add("pcie")

    if "NVME" in s:
        classes.add("nvme")

    if any(x in s for x in [
        "USB_EHCI",
        "USB_OHCI",
        "USB_XHCI",
        "USB_DWC3",
    ]):
        classes.add("usb-host")

    if any(x in s for x in [
        "USB2",
        "USBDP",
        "USB_PHY",
        "TYPEC",
    ]):
        classes.add("usb-phy")

    if "USB_STORAGE" in s:
        classes.add("usb-storage")

    return classes


def load_driver_symbols(path):
    symbols = set()

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            if not line:
                continue

            parts = line.split("\t")

            if len(parts) < 2:
                continue

            symbol = parts[1]

            if symbol.startswith("CONFIG_"):
                symbols.add(symbol)

    return symbols


def write_fragment(path, values):
    lines = []

    for symbol in sorted(values):
        value = values[symbol]

        if value == "n":
            lines.append(f"# {symbol} is not set")
        else:
            lines.append(f"{symbol}={value}")

    path.write_text(
        "\n".join(lines) + ("\n" if lines else ""),
        encoding="utf-8"
    )


def run_merge(kernel, vyos_config, fragment, output_config):
    kernel = Path(kernel)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        temp_config = tmpdir / ".config"

        env = dict(**__import__("os").environ)
        env["ARCH"] = "arm64"
        env["KCONFIG_CONFIG"] = str(temp_config)

        subprocess.run(
            [
                str(kernel / "scripts/kconfig/merge_config.sh"),
                "-m",
                str(vyos_config),
                str(fragment),
            ],
            cwd=kernel,
            env=env,
            check=True,
        )

        #
        # Always run Kbuild out-of-tree.
        #
        # The kernel source cache must remain pristine because the same
        # source tree is reused for multiple boards.
        #
        subprocess.run(
            [
                "make",
                "-C",
                str(kernel),
                f"O={tmpdir}",
                "ARCH=arm64",
                "olddefconfig",
            ],
            env=env,
            check=True,
        )

        output_config.write_text(
            temp_config.read_text(encoding="utf-8"),
            encoding="utf-8"
        )


def run_kconfig_closure(kernel, vyos_config, raw_fragment, out):
    closure_tool = (
        Path(__file__).resolve().parent
        / "kconfig-closure.py"
    )

    closure_dir = out / "kconfig-closure"

    if closure_dir.exists():
        import shutil
        shutil.rmtree(closure_dir)

    subprocess.run(
        [
            str(closure_tool),
            "--kernel",
            str(kernel),
            "--base-config",
            str(vyos_config),
            "--requested",
            str(raw_fragment),
            "--output",
            str(closure_dir),
        ],
        check=True,
    )

    unresolved = closure_dir / "unresolved.txt"

    if unresolved.exists() and unresolved.stat().st_size:
        text = unresolved.read_text(
            encoding="utf-8"
        )

        raise SystemExit(
            "Unresolved Kconfig dependencies:\n"
            + text
        )

    resolved = (
        closure_dir
        / "resolved-fragment.config"
    )

    if not resolved.is_file():
        raise SystemExit(
            f"Kconfig closure produced no fragment: {resolved}"
        )

    return resolved

def scan_kconfig_symbols(kernel):
    config_re = re.compile(
        r'^(?:config|menuconfig)\s+([A-Za-z0-9_]+)\s*$'
    )
    select_re = re.compile(
        r'^\s*select\s+([A-Za-z0-9_]+)(?:\s+if\s+(.+))?\s*$'
    )

    defs = {}
    reverse_select = {}

    kernel_path = Path(kernel)

    for path in kernel_path.rglob("Kconfig*"):
        if not path.is_file():
            continue

        rel = path.relative_to(kernel_path)

        if len(rel.parts) >= 2 and rel.parts[0] == "arch":
            if rel.parts[1] == "arm":
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

            entry = defs.setdefault(
                symbol,
                {
                    "prompt": False,
                    "selects": [],
                }
            )

            for line in block_lines:
                stripped = line.strip()

                if re.match(
                    r'^(bool|tristate|string|int|hex)\s+"',
                    stripped
                ):
                    entry["prompt"] = True

                m = select_re.match(line)

                if m:
                    target = m.group(1)
                    condition = m.group(2)

                    entry["selects"].append(
                        (target, condition)
                    )

                    reverse_select.setdefault(
                        target, []
                    ).append(
                        (symbol, condition)
                    )

        for line in lines:
            m = config_re.match(line)

            if m:
                store(current, block)
                current = m.group(1)
                block = [line]
            elif current:
                block.append(line)

        store(current, block)

    return defs, reverse_select


def resolve_visible_frontend(symbol, defs, reverse_select):
    raw = symbol.removeprefix("CONFIG_")

    data = defs.get(raw)

    if not data:
        return symbol

    if data.get("prompt"):
        return symbol

    candidates = []

    for selector, condition in reverse_select.get(raw, []):
        selector_data = defs.get(selector, {})

        if selector_data.get("prompt"):
            candidates.append(selector)

    if len(candidates) == 1:
        return "CONFIG_" + candidates[0]

    #
    # Common Kconfig pattern for PCIe controller cores:
    #
    #   CONFIG_FOO          (internal)
    #      selected by:
    #        CONFIG_FOO_HOST
    #        CONFIG_FOO_EP
    #
    # A normal board DT describes the host controller. Endpoint
    # operation requires an explicit endpoint configuration.
    #
    if len(candidates) > 1:
        host_candidates = [
            c for c in candidates
            if c.endswith("_HOST")
        ]

        ep_candidates = [
            c for c in candidates
            if c.endswith("_EP")
        ]

        if len(host_candidates) == 1 and ep_candidates:
            return "CONFIG_" + host_candidates[0]

    return symbol

def main():
    parser = argparse.ArgumentParser(
        description="Generate a boot-oriented board Kconfig fragment"
    )

    parser.add_argument("--kernel", required=True)
    parser.add_argument("--vyos-config", required=True)
    parser.add_argument("--reference-config")
    parser.add_argument("--driver-map", required=True)
    parser.add_argument("--boot-profile", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--boot-media", required=True)
    parser.add_argument("--output-dir", required=True)

    args = parser.parse_args()

    kernel = Path(args.kernel)
    vyos_config = Path(args.vyos_config)
    driver_map = Path(args.driver_map)
    out = Path(args.output_dir)

    out.mkdir(parents=True, exist_ok=True)

    profile = read_boot_profile(args.boot_profile)
    policy = read_policy(args.policy)

    requested_media = [
        x.strip()
        for x in args.boot_media.split(",")
        if x.strip()
    ]

    required_classes = set()
    endpoint_symbols = set()

    for medium in requested_media:
        if medium not in profile:
            raise SystemExit(
                f"Unknown boot medium: {medium}"
            )

        required_classes.update(
            profile[medium]["required_classes"]
        )

        endpoint_symbols.update(
            profile[medium]["endpoint_symbols"]
        )

    driver_symbols = load_driver_symbols(driver_map)

    #
    # Current VyOS state is needed not only for final validation but
    # also for runtime hardware policy.  Active DTB hardware whose
    # driver is already y/m is preserved; an unavailable driver must
    # be added to the board fragment.
    #
    vyos_values = read_config(vyos_config)

    reference_values = {}

    if args.reference_config:
        reference_values = read_config(
            Path(args.reference_config)
        )

    kconfig_defs, reverse_select = scan_kconfig_symbols(
        kernel
    )

    resolved_driver_symbols = set()

    for symbol in driver_symbols:
        resolved_driver_symbols.add(
            resolve_visible_frontend(
                symbol,
                kconfig_defs,
                reverse_select
            )
        )

    driver_symbols = resolved_driver_symbols

    selected = {}

    for symbol in sorted(endpoint_symbols):
        selected[symbol] = policy.get(
            "BOOT_CRITICAL_MODE",
            "y"
        )

    boot_mode = policy.get(
        "BOOT_CRITICAL_MODE",
        "y"
    )

    runtime_mode = policy.get(
        "RUNTIME_MODE",
        "preserve"
    )

    for symbol in sorted(driver_symbols):
        classes = classify_symbol(symbol)

        #
        # Hardware required to reach a requested root filesystem must
        # be built into the kernel.
        #
        if classes & required_classes:
            selected[symbol] = boot_mode
            continue

        #
        # All remaining symbols still came from active DTB nodes.
        #
        # "preserve" means:
        #
        #   VyOS y  -> leave untouched
        #   VyOS m  -> leave untouched
        #   VyOS n  -> enable, because otherwise active board
        #              hardware would have no driver at all
        #
        # We currently promote missing runtime hardware to y.  This
        # gives kconfig-closure.py a deterministic dependency target
        # and is safe for platform infrastructure such as clocks and
        # pinctrl.  Later we can add tristate-aware m preservation
        # without changing the DTB selection model.
        #
        if runtime_mode == "preserve":
            current = vyos_values.get(symbol, "n")

            #
            # Existing VyOS y/m values are already usable and are
            # therefore left untouched.
            #
            if current == "n":
                reference = reference_values.get(
                    symbol,
                    "n"
                )

                #
                # For runtime-only hardware preserve the tristate
                # chosen by the known-good reference kernel.
                #
                # Boot-critical drivers never reach this block:
                # they were already promoted to boot_mode above.
                #
                if reference in ("y", "m"):
                    selected[symbol] = reference

                #
                # Backward compatibility for callers without a
                # reference config: retain the previous behaviour.
                #
                elif not args.reference_config:
                    selected[symbol] = "y"

        elif runtime_mode in ("y", "m"):
            selected[symbol] = runtime_mode

        else:
            raise SystemExit(
                f"Unknown RUNTIME_MODE: {runtime_mode}"
            )

    #
    # Add small generic infrastructure symbols where a boot class
    # logically requires them.
    #
    if "mmc" in required_classes:
        for symbol in [
            "CONFIG_MMC",
            "CONFIG_MMC_DW",
            "CONFIG_MMC_SDHCI",
            "CONFIG_MMC_SDHCI_PLTFM",
        ]:
            selected[symbol] = boot_mode

    if "usb-phy" in required_classes:
        selected["CONFIG_TYPEC"] = boot_mode

    raw_fragment = out / "generated-board.raw.config"
    write_fragment(raw_fragment, selected)

    resolved_fragment = run_kconfig_closure(
        kernel=kernel,
        vyos_config=vyos_config,
        raw_fragment=raw_fragment,
        out=out,
    )

    fragment = out / "generated-board.config"

    fragment.write_text(
        resolved_fragment.read_text(encoding="utf-8"),
        encoding="utf-8"
    )

    final_config = out / "generated-final.config"

    run_merge(
        kernel=kernel,
        vyos_config=vyos_config,
        fragment=fragment,
        output_config=final_config,
    )

    requested = read_config(fragment)
    final = read_config(final_config)

    report = []

    ok = 0
    bad = 0

    for symbol in sorted(requested):
        want = requested[symbol]
        got = final.get(symbol, "n")

        state = "OK" if want == got else "FAIL"

        if state == "OK":
            ok += 1
        else:
            bad += 1

        report.append(
            f"{state:5} {symbol:45} requested={want:3} final={got}"
        )

    report_path = out / "validation.txt"
    report_path.write_text(
        "\n".join(report) + "\n",
        encoding="utf-8"
    )

    print()
    print("Generic board config generation")
    print("-------------------------------")
    print(f"Boot media:       {','.join(requested_media)}")
    print(f"Required classes: {','.join(sorted(required_classes))}")
    print(f"Driver symbols:   {len(driver_symbols)}")
    print(f"Selected symbols: {len(selected)}")
    print(f"Validation OK:    {ok}")
    print(f"Validation FAIL:  {bad}")
    print()
    print(f"Fragment:   {fragment}")
    print(f"Final:      {final_config}")
    print(f"Validation: {report_path}")


if __name__ == "__main__":
    main()
