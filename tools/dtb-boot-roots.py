#!/usr/bin/env python3

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_driver_map(path):
    result = defaultdict(list)

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")

            if len(parts) < 3:
                continue

            compatible, config, source = parts[:3]

            row = {
                "compatible": compatible,
                "config": config,
                "source": source,
            }

            if row not in result[compatible]:
                result[compatible].append(row)

    return result


class DtbReader:
    def __init__(self, dtb):
        self.dtb = str(dtb)
        self.props_cache = {}
        self.string_cache = {}

    def properties(self, path):
        if path in self.props_cache:
            return self.props_cache[path]

        proc = subprocess.run(
            [
                "fdtget",
                "-p",
                self.dtb,
                path,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        if proc.returncode:
            props = set()
        else:
            props = {
                line.strip()
                for line in proc.stdout.splitlines()
                if line.strip()
            }

        self.props_cache[path] = props

        return props

    def string(self, path, prop):
        key = (path, prop)

        if key in self.string_cache:
            return self.string_cache[key]

        proc = subprocess.run(
            [
                "fdtget",
                "-t",
                "s",
                self.dtb,
                path,
                prop,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        value = (
            proc.stdout.strip()
            if proc.returncode == 0
            else None
        )

        self.string_cache[key] = value

        return value


def rows_for_node(node, mapping):
    result = []

    for compatible in node.get(
        "compatible",
        [],
    ):
        for row in mapping.get(
            compatible,
            [],
        ):
            if row not in result:
                result.append(row)

    return result


def looks_like_mmc(path, node):
    if "/mmc@" in path:
        return True

    return any(
        "mmc" in compatible.lower()
        or "sdhci" in compatible.lower()
        for compatible
        in node.get("compatible", [])
    )


def classify_mmc(path, node, dtb):
    props = dtb.properties(path)

    non_removable = (
        "non-removable" in props
    )

    supports_sd = (
        "no-sd" not in props
    )

    supports_mmc = (
        "no-mmc" not in props
    )

    supports_sdio = (
        "no-sdio" not in props
    )

    media = []

    #
    # A removable controller which accepts SD cards is
    # a physical SD-card boot candidate.
    #
    # Do not require cd-gpios: some controllers have
    # native card-detect or deliberately use broken-cd.
    #
    if (
        supports_sd
        and not non_removable
    ):
        media.append(
            (
                "sd",
                "removable-sd-controller",
            )
        )

    #
    # A non-removable controller with MMC support and
    # explicit lack of SD support is an eMMC candidate.
    #
    # Pure soldered SDIO devices should describe
    # no-mmc and therefore do not enter this branch.
    #
    if (
        non_removable
        and supports_mmc
        and not supports_sd
    ):
        media.append(
            (
                "emmc",
                "non-removable-mmc-controller",
            )
        )

    #
    # Record SDIO-only devices diagnostically. They are
    # deliberately not boot roots for sd/emmc.
    #
    sdio_only = (
        non_removable
        and supports_sdio
        and not supports_sd
        and not supports_mmc
    )

    return {
        "media": media,
        "sdio_only": sdio_only,
        "non_removable": non_removable,
        "supports_sd": supports_sd,
        "supports_mmc": supports_mmc,
        "supports_sdio": supports_sdio,
    }


def classify_pcie(path, node, mapping, dtb):
    rows = rows_for_node(
        node,
        mapping,
    )

    controller_rows = [
        row
        for row in rows
        if row["source"].startswith(
            "drivers/pci/controller/"
        )
    ]

    if not controller_rows:
        return None

    props = dtb.properties(path)

    device_type = dtb.string(
        path,
        "device_type",
    )

    #
    # Standard PCI host bridges generally advertise
    # device_type = "pci".  Some platform DTs omit it,
    # so the presence of host-bridge address/range
    # properties is accepted as equivalent evidence.
    #
    host_evidence = (
        device_type in {
            "pci",
            "pcie",
        }
        or (
            "bus-range" in props
            and "ranges" in props
        )
    )

    if not host_evidence:
        return None

    return {
        "medium": "nvme",
        "reason": "active-pcie-host-controller",
        "device_type": device_type,
        "drivers": controller_rows,
    }


def classify_usb(path, node, mapping, dtb):
    rows = rows_for_node(
        node,
        mapping,
    )

    host_rows = [
        row
        for row in rows
        if row["source"].startswith(
            "drivers/usb/host/"
        )
    ]

    if host_rows:
        return {
            "medium": "usb",
            "reason": "usb-host-controller",
            "dr_mode": None,
            "drivers": host_rows,
        }

    dwc3_rows = [
        row
        for row in rows
        if (
            row["source"].startswith(
                "drivers/usb/dwc3/"
            )
            and row["config"].startswith(
                "CONFIG_USB_DWC3"
            )
        )
    ]

    if not dwc3_rows:
        return None

    dr_mode = dtb.string(
        path,
        "dr_mode",
    )

    #
    # A DWC3 peripheral-only controller cannot boot from
    # USB storage.
    #
    # "host", "otg", or an unspecified role remain
    # host-capable and are retained. OTG may require
    # role-switch/Type-C suppliers, which is precisely
    # why it belongs in the dependency graph.
    #
    if dr_mode == "peripheral":
        return None

    return {
        "medium": "usb",
        "reason": (
            "dwc3-host-capable"
            if dr_mode != "otg"
            else "dwc3-otg-host-capable"
        ),
        "dr_mode": dr_mode,
        "drivers": dwc3_rows,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Derive concrete DT boot-root nodes for "
            "requested storage media without board-"
            "specific controller addresses."
        )
    )

    parser.add_argument(
        "--dtb",
        required=True,
    )

    parser.add_argument(
        "--graph",
        required=True,
    )

    parser.add_argument(
        "--driver-map",
        required=True,
    )

    parser.add_argument(
        "--boot-media",
        required=True,
        help=(
            "Comma-separated list: "
            "sd,emmc,nvme,usb"
        ),
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    args = parser.parse_args()

    requested = []

    for item in args.boot_media.split(","):
        item = item.strip()

        if not item:
            continue

        if item not in {
            "sd",
            "emmc",
            "nvme",
            "usb",
        }:
            raise SystemExit(
                f"Unknown boot medium: {item}"
            )

        if item not in requested:
            requested.append(item)

    graph = load_json(
        args.graph
    )

    mapping = load_driver_map(
        args.driver_map
    )

    dtb = DtbReader(
        args.dtb
    )

    roots_by_medium = {
        medium: []
        for medium in requested
    }

    evidence = []
    ignored = []

    for path, node in sorted(
        graph["nodes"].items()
    ):
        if looks_like_mmc(
            path,
            node,
        ):
            info = classify_mmc(
                path,
                node,
                dtb,
            )

            for medium, reason in info[
                "media"
            ]:
                if medium not in roots_by_medium:
                    continue

                roots_by_medium[
                    medium
                ].append(path)

                evidence.append(
                    {
                        "medium": medium,
                        "path": path,
                        "reason": reason,
                        "compatible": node.get(
                            "compatible",
                            [],
                        ),
                        "details": {
                            "non_removable":
                                info[
                                    "non_removable"
                                ],
                            "supports_sd":
                                info[
                                    "supports_sd"
                                ],
                            "supports_mmc":
                                info[
                                    "supports_mmc"
                                ],
                            "supports_sdio":
                                info[
                                    "supports_sdio"
                                ],
                        },
                    }
                )

            if info["sdio_only"]:
                ignored.append(
                    {
                        "path": path,
                        "reason":
                            "non-removable-sdio-only",
                        "compatible": node.get(
                            "compatible",
                            [],
                        ),
                    }
                )

        if "nvme" in roots_by_medium:
            pcie = classify_pcie(
                path,
                node,
                mapping,
                dtb,
            )

            if pcie:
                roots_by_medium[
                    "nvme"
                ].append(path)

                evidence.append(
                    {
                        "medium": "nvme",
                        "path": path,
                        "reason": pcie[
                            "reason"
                        ],
                        "compatible": node.get(
                            "compatible",
                            [],
                        ),
                        "details": {
                            "device_type":
                                pcie[
                                    "device_type"
                                ],
                            "drivers":
                                pcie[
                                    "drivers"
                                ],
                        },
                    }
                )

        if "usb" in roots_by_medium:
            usb = classify_usb(
                path,
                node,
                mapping,
                dtb,
            )

            if usb:
                roots_by_medium[
                    "usb"
                ].append(path)

                evidence.append(
                    {
                        "medium": "usb",
                        "path": path,
                        "reason": usb[
                            "reason"
                        ],
                        "compatible": node.get(
                            "compatible",
                            [],
                        ),
                        "details": {
                            "dr_mode":
                                usb[
                                    "dr_mode"
                                ],
                            "drivers":
                                usb[
                                    "drivers"
                                ],
                        },
                    }
                )

    for medium in roots_by_medium:
        roots_by_medium[medium] = sorted(
            set(
                roots_by_medium[
                    medium
                ]
            )
        )

    all_roots = sorted(
        {
            path
            for roots
            in roots_by_medium.values()
            for path in roots
        }
    )

    outdir = Path(
        args.output_dir
    )

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    txt_out = (
        outdir /
        "boot-roots.txt"
    )

    txt_out.write_text(
        "".join(
            f"{path}\n"
            for path in all_roots
        ),
        encoding="utf-8",
    )

    map_out = (
        outdir /
        "boot-root-map.tsv"
    )

    with map_out.open(
        "w",
        encoding="utf-8",
    ) as f:
        for item in sorted(
            evidence,
            key=lambda x: (
                x["medium"],
                x["path"],
            ),
        ):
            print(
                item["medium"],
                item["path"],
                item["reason"],
                ",".join(
                    item.get(
                        "compatible",
                        [],
                    )
                ),
                sep="\t",
                file=f,
            )

    json_out = (
        outdir /
        "boot-roots.json"
    )

    json_out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "requested_media":
                    requested,
                "root_count":
                    len(all_roots),
                "roots":
                    all_roots,
                "roots_by_medium":
                    roots_by_medium,
                "evidence":
                    evidence,
                "ignored":
                    ignored,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("DT boot-root discovery")
    print("----------------------")

    print(
        "Requested media: "
        + ",".join(requested)
    )

    for medium in requested:
        roots = roots_by_medium[
            medium
        ]

        print(
            f"{medium:5s}: "
            f"{len(roots)} root(s)"
        )

        for root in roots:
            print(
                f"  {root}"
            )

    print(
        f"Unique roots: {len(all_roots)}"
    )

    print(
        f"Roots:   {txt_out}"
    )
    print(
        f"Map:     {map_out}"
    )
    print(
        f"Context: {json_out}"
    )


if __name__ == "__main__":
    main()
