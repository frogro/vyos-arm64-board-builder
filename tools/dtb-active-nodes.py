#!/usr/bin/env python3

import argparse
import json
import subprocess
from pathlib import Path


def run(*args):
    p = subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return p.stdout.strip()


def children(dtb, path):
    out = run("fdtget", "-l", dtb, path)
    return [x for x in out.splitlines() if x.strip()]


def get_string(dtb, path, prop):
    return run("fdtget", "-t", "s", dtb, path, prop)


def get_cells(dtb, path, prop):
    out = run("fdtget", "-t", "x", dtb, path, prop)
    return out if out else ""


def prop_exists(dtb, path, prop):
    p = subprocess.run(
        ["fdtget", dtb, path, prop],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return p.returncode == 0


def walk(dtb, path="/", parent_unavailable=False):
    status = get_string(dtb, path, "status")

    # DT nodes are available when status is absent or explicitly
    # "okay"/"ok".  disabled/fail/reserved/etc. are unavailable,
    # and their complete subtree must be ignored.
    locally_available = (
        not status
        or status in ("okay", "ok")
    )

    unavailable = parent_unavailable or not locally_available

    if not unavailable:
        compat_raw = get_string(dtb, path, "compatible")

        compatibles = [
            x for x in compat_raw.split()
            if x
        ]

        if compatibles:
            yield {
                "path": path,
                "compatible": compatibles,
                "status": status or "okay",
                "non_removable": prop_exists(
                    dtb, path, "non-removable"
                ),
                "bus_width": get_cells(
                    dtb, path, "bus-width"
                ),
                "reg": get_cells(
                    dtb, path, "reg"
                ),
                "phys": get_cells(
                    dtb, path, "phys"
                ),
                "vmmc_supply": get_cells(
                    dtb, path, "vmmc-supply"
                ),
                "vqmmc_supply": get_cells(
                    dtb, path, "vqmmc-supply"
                ),
            }

    for child in children(dtb, path):
        child_path = (
            f"/{child}"
            if path == "/"
            else f"{path}/{child}"
        )

        yield from walk(
            dtb,
            child_path,
            unavailable
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dtb", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    nodes = list(walk(args.dtb))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(
        json.dumps(
            nodes,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Active compatible nodes: {len(nodes)}")
    print(f"Output: {out}")


if __name__ == "__main__":
    main()
