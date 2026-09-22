#!/usr/bin/env python3

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


SERVICE_SOURCE_PREFIXES = {
    "regulator": ("drivers/regulator/",),
    "pinctrl": ("drivers/pinctrl/",),
    "gpio": ("drivers/gpio/",),
    "clk": ("drivers/clk/",),
    "reset": ("drivers/reset/",),
    "phy": ("drivers/phy/",),
    "pwm": ("drivers/pwm/",),
    "dma": ("drivers/dma/",),
    "mailbox": ("drivers/mailbox/",),
    "iommu": ("drivers/iommu/",),
    "interconnect": ("drivers/interconnect/",),
    "pmdomain": ("drivers/pmdomain/",),
}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def property_service(prop):
    if not prop:
        return None

    if prop.endswith("-supply"):
        return "regulator"

    if re.fullmatch(r"pinctrl-\d+", prop):
        return "pinctrl"

    if (
        prop == "gpios"
        or prop.endswith("-gpios")
    ):
        return "gpio"

    if prop in {
        "clocks",
        "assigned-clocks",
        "assigned-clock-parents",
    }:
        return "clk"

    if prop == "resets":
        return "reset"

    if prop == "phys":
        return "phy"

    if prop == "pwms":
        return "pwm"

    if prop == "dmas":
        return "dma"

    if prop == "mboxes":
        return "mailbox"

    if prop == "iommus":
        return "iommu"

    if prop == "interconnects":
        return "interconnect"

    if prop == "power-domains":
        return "pmdomain"

    return None


def load_mfd_children(path):
    by_parent = defaultdict(list)

    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")

            if len(parts) < 6:
                continue

            origin, config, child_source, variant, core_source, array = (
                parts[:6]
            )

            if not origin.startswith("mfd:"):
                continue

            origin_parts = origin.split(":", 2)

            if len(origin_parts) != 3:
                continue

            parent_source = origin_parts[1]
            child_name = origin_parts[2]

            row = {
                "origin": origin,
                "parent_source": parent_source,
                "child_name": child_name,
                "config": config,
                "child_source": child_source,
                "variant": variant,
                "core_source": core_source,
                "array": array,
            }

            by_parent[parent_source].append(row)

    return by_parent


def service_matches_source(service, source):
    prefixes = SERVICE_SOURCE_PREFIXES.get(
        service,
        (),
    )

    return any(
        source.startswith(prefix)
        for prefix in prefixes
    )


def target_is_internal(provider, target):
    if not provider or not target:
        return False

    prefix = provider.rstrip("/") + "/"

    return target.startswith(prefix)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve required MFD child services from "
            "DT supplier edges without enabling every "
            "child produced by an active MFD."
        )
    )

    parser.add_argument(
        "--closure",
        required=True,
    )

    parser.add_argument(
        "--driver-context",
        required=True,
    )

    parser.add_argument(
        "--mfd-map",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    args = parser.parse_args()

    closure = load_json(args.closure)
    context = load_json(args.driver_context)
    mfd_children = load_mfd_children(
        args.mfd_map
    )

    driver_by_path = {
        item["path"]: item
        for item in context.get("resolved", [])
    }

    resolved = []
    unresolved = []
    ignored = []

    for edge in closure.get("edges", []):
        prop = edge.get("property")
        service = property_service(prop)

        if not service:
            continue

        provider_path = edge.get(
            "provider_path"
        )

        target_path = edge.get(
            "target_path"
        )

        #
        # MFD-produced services are relevant here only
        # when the DT target is an internal descendant
        # of the provider node itself.
        #
        if not target_is_internal(
            provider_path,
            target_path,
        ):
            continue

        provider_driver = driver_by_path.get(
            provider_path
        )

        if not provider_driver:
            ignored.append({
                "consumer": edge.get("consumer"),
                "property": prop,
                "service": service,
                "target_path": target_path,
                "provider_path": provider_path,
                "reason": (
                    "provider-has-no-resolved-driver"
                ),
            })
            continue

        selected = provider_driver.get(
            "selected",
            {},
        )

        parent_source = selected.get(
            "source"
        )

        if not parent_source:
            continue

        children = mfd_children.get(
            parent_source,
            [],
        )

        #
        # If this source is not an MFD parent represented
        # by the child map, this is not an MFD-service edge.
        #
        if not children:
            continue

        candidates = [
            child
            for child in children
            if service_matches_source(
                service,
                child["child_source"],
            )
        ]

        evidence = {
            "consumer": edge.get("consumer"),
            "property": prop,
            "service": service,
            "target_path": target_path,
            "provider_path": provider_path,
            "parent_config": selected.get(
                "config"
            ),
            "parent_source": parent_source,
        }

        if len(candidates) == 1:
            child = candidates[0]

            resolved.append({
                **evidence,
                "child_name": child[
                    "child_name"
                ],
                "config": child["config"],
                "child_source": child[
                    "child_source"
                ],
                "variant": child["variant"],
                "core_source": child[
                    "core_source"
                ],
                "array": child["array"],
                "resolution": (
                    "unique-service-child"
                ),
            })

            continue

        if not candidates:
            unresolved.append({
                **evidence,
                "reason": (
                    "no-child-for-service"
                ),
                "candidates": [],
            })
            continue

        unresolved.append({
            **evidence,
            "reason": (
                "ambiguous-children-for-service"
            ),
            "candidates": candidates,
        })

    #
    # Deduplicate repeated DT references while preserving
    # all evidence in the JSON result.
    #
    unique_configs = {}

    for item in resolved:
        key = (
            item["config"],
            item["child_source"],
            item["parent_source"],
        )

        unique_configs.setdefault(
            key,
            {
                "config": item["config"],
                "child_source": item[
                    "child_source"
                ],
                "parent_source": item[
                    "parent_source"
                ],
                "services": set(),
                "properties": set(),
                "providers": set(),
            },
        )

        entry = unique_configs[key]

        entry["services"].add(
            item["service"]
        )
        entry["properties"].add(
            item["property"]
        )
        entry["providers"].add(
            item["provider_path"]
        )

    outdir = Path(args.output_dir)

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "schema_version": 1,
        "source_closure": str(
            Path(args.closure)
        ),
        "source_driver_context": str(
            Path(args.driver_context)
        ),
        "resolved_edge_count": len(
            resolved
        ),
        "unresolved_edge_count": len(
            unresolved
        ),
        "unique_config_count": len(
            unique_configs
        ),
        "resolved": resolved,
        "unresolved": unresolved,
        "ignored": ignored,
    }

    json_out = (
        outdir /
        "mfd-service-context.json"
    )

    json_out.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    map_out = (
        outdir /
        "mfd-service-config-map.tsv"
    )

    with map_out.open(
        "w",
        encoding="utf-8",
    ) as f:
        for key in sorted(
            unique_configs
        ):
            entry = unique_configs[key]

            print(
                entry["config"],
                entry["child_source"],
                entry["parent_source"],
                ",".join(
                    sorted(
                        entry["services"]
                    )
                ),
                ",".join(
                    sorted(
                        entry["properties"]
                    )
                ),
                ",".join(
                    sorted(
                        entry["providers"]
                    )
                ),
                sep="\t",
                file=f,
            )

    symbols_out = (
        outdir /
        "mfd-service-config-symbols.txt"
    )

    symbols_out.write_text(
        "".join(
            f"{entry['config']}\n"
            for _, entry in sorted(
                unique_configs.items()
            )
        ),
        encoding="utf-8",
    )

    unresolved_out = (
        outdir /
        "unresolved-mfd-services.json"
    )

    unresolved_out.write_text(
        json.dumps(
            unresolved,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("DT MFD service resolution")
    print("-------------------------")
    print(
        f"Resolved service edges:   "
        f"{len(resolved)}"
    )
    print(
        f"Unresolved service edges: "
        f"{len(unresolved)}"
    )
    print(
        f"Unique CONFIG symbols:    "
        f"{len(unique_configs)}"
    )

    for _, entry in sorted(
        unique_configs.items()
    ):
        print(
            "  "
            f"{entry['config']} "
            f"[{','.join(sorted(entry['services']))}] "
            f"{entry['child_source']}"
        )

    print(f"Context: {json_out}")
    print(f"Map:     {map_out}")
    print(f"Symbols: {symbols_out}")


if __name__ == "__main__":
    main()
