#!/usr/bin/env python3

import argparse
import json
import subprocess
from pathlib import Path


PHANDLE_ARRAY_PROPERTIES = {
    "clocks": "#clock-cells",
    "assigned-clocks": "#clock-cells",
    "assigned-clock-parents": "#clock-cells",
    "resets": "#reset-cells",
    "power-domains": "#power-domain-cells",
    "phys": "#phy-cells",
    "iommus": "#iommu-cells",
    "dmas": "#dma-cells",
    "mboxes": "#mbox-cells",
    "pwms": "#pwm-cells",
    "interconnects": "#interconnect-cells",
    "interrupts-extended": "#interrupt-cells",
}


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
    return [x.strip() for x in out.splitlines() if x.strip()]


def properties(dtb, path):
    out = run("fdtget", "-p", dtb, path)
    return [x.strip() for x in out.splitlines() if x.strip()]


def get_string(dtb, path, prop):
    return run("fdtget", "-t", "s", dtb, path, prop)


def get_cells_text(dtb, path, prop):
    return run("fdtget", "-t", "x", dtb, path, prop)


def get_cells(dtb, path, prop):
    raw = get_cells_text(dtb, path, prop)
    if not raw:
        return []

    result = []

    for value in raw.split():
        try:
            result.append(int(value, 16))
        except ValueError:
            pass

    return result


def prop_exists(dtb, path, prop):
    p = subprocess.run(
        ["fdtget", dtb, path, prop],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return p.returncode == 0


def node_available(dtb, path):
    status = get_string(dtb, path, "status")

    return (
        not status
        or status in ("okay", "ok")
    )


def walk_all(dtb, path="/", parent_unavailable=False):
    locally_available = node_available(dtb, path)
    unavailable = parent_unavailable or not locally_available

    yield {
        "path": path,
        "status": get_string(dtb, path, "status") or "okay",
        "available": not unavailable,
    }

    for child in children(dtb, path):
        child_path = (
            f"/{child}"
            if path == "/"
            else f"{path}/{child}"
        )

        yield from walk_all(
            dtb,
            child_path,
            unavailable,
        )


def compatibles(dtb, path):
    raw = get_string(dtb, path, "compatible")

    return [
        value
        for value in raw.split()
        if value
    ]


def parent_path(path):
    if path == "/":
        return None

    parent = path.rsplit("/", 1)[0]
    return parent or "/"


def nearest_compatible_ancestor(dtb, path):
    current = path

    while current:
        comp = compatibles(dtb, current)

        if comp:
            return current, comp

        current = parent_path(current)

    return None, []


def build_phandle_index(dtb, all_nodes):
    result = {}

    for node in all_nodes:
        path = node["path"]

        for prop in ("phandle", "linux,phandle"):
            values = get_cells(dtb, path, prop)

            if values:
                result[values[0]] = path

    return result


def provider_cell_count(dtb, provider, cell_property):
    values = get_cells(dtb, provider, cell_property)

    if not values:
        return None

    return values[0]


def supplier_record(
    dtb,
    phandles,
    all_node_map,
    prop,
    phandle,
    args,
    parse_error=None,
):
    target = phandles.get(phandle)

    record = {
        "property": prop,
        "phandle": f"0x{phandle:x}",
        "args": [
            f"0x{value:x}"
            for value in args
        ],
        "target_path": target,
        "target_compatible": [],
        "target_available": None,
        "provider_path": None,
        "provider_compatible": [],
    }

    if parse_error:
        record["parse_error"] = parse_error

    if not target:
        record["parse_error"] = (
            record.get("parse_error")
            or "unresolved-phandle"
        )
        return record

    record["target_compatible"] = compatibles(dtb, target)

    if target in all_node_map:
        record["target_available"] = all_node_map[target][
            "available"
        ]

    provider, provider_compatible = (
        nearest_compatible_ancestor(dtb, target)
    )

    record["provider_path"] = provider
    record["provider_compatible"] = provider_compatible

    return record


def parse_phandle_array(
    dtb,
    path,
    prop,
    cell_property,
    phandles,
    all_node_map,
):
    values = get_cells(dtb, path, prop)
    result = []

    index = 0

    while index < len(values):
        phandle = values[index]
        target = phandles.get(phandle)

        if not target:
            result.append(
                supplier_record(
                    dtb,
                    phandles,
                    all_node_map,
                    prop,
                    phandle,
                    [],
                    "unknown-provider-phandle",
                )
            )
            index += 1
            continue

        cell_count = provider_cell_count(
            dtb,
            target,
            cell_property,
        )

        if cell_count is None:
            result.append(
                supplier_record(
                    dtb,
                    phandles,
                    all_node_map,
                    prop,
                    phandle,
                    [],
                    f"provider-missing-{cell_property}",
                )
            )

            # We cannot safely interpret subsequent cells as new
            # phandles without the provider's cell count.
            break

        end = index + 1 + cell_count

        if end > len(values):
            result.append(
                supplier_record(
                    dtb,
                    phandles,
                    all_node_map,
                    prop,
                    phandle,
                    values[index + 1:],
                    "truncated-provider-specifier",
                )
            )
            break

        args = values[index + 1:end]

        result.append(
            supplier_record(
                dtb,
                phandles,
                all_node_map,
                prop,
                phandle,
                args,
            )
        )

        index = end

    return result


def parse_plain_phandles(
    dtb,
    path,
    prop,
    phandles,
    all_node_map,
):
    return [
        supplier_record(
            dtb,
            phandles,
            all_node_map,
            prop,
            phandle,
            [],
        )
        for phandle in get_cells(dtb, path, prop)
    ]


def node_suppliers(
    dtb,
    path,
    phandles,
    all_node_map,
):
    result = []

    for prop in properties(dtb, path):
        if prop in PHANDLE_ARRAY_PROPERTIES:
            result.extend(
                parse_phandle_array(
                    dtb,
                    path,
                    prop,
                    PHANDLE_ARRAY_PROPERTIES[prop],
                    phandles,
                    all_node_map,
                )
            )
            continue

        # pinctrl-N contains plain phandles to state/group nodes.
        if (
            prop.startswith("pinctrl-")
            and prop != "pinctrl-names"
        ):
            result.extend(
                parse_plain_phandles(
                    dtb,
                    path,
                    prop,
                    phandles,
                    all_node_map,
                )
            )
            continue

        # Regulator supply properties contain one phandle.
        if prop.endswith("-supply"):
            values = get_cells(dtb, path, prop)

            if values:
                result.append(
                    supplier_record(
                        dtb,
                        phandles,
                        all_node_map,
                        prop,
                        values[0],
                        [],
                    )
                )
            continue

        # GPIO properties use provider-specific #gpio-cells.
        if prop == "gpios" or prop.endswith("-gpios"):
            result.extend(
                parse_phandle_array(
                    dtb,
                    path,
                    prop,
                    "#gpio-cells",
                    phandles,
                    all_node_map,
                )
            )
            continue

        # Explicit interrupt parent is a single phandle.
        if prop == "interrupt-parent":
            values = get_cells(dtb, path, prop)

            if values:
                result.append(
                    supplier_record(
                        dtb,
                        phandles,
                        all_node_map,
                        prop,
                        values[0],
                        [],
                    )
                )

    return result


def compatible_node_record(dtb, path):
    return {
        "path": path,
        "compatible": compatibles(dtb, path),
        "status": get_string(dtb, path, "status") or "okay",
        "non_removable": prop_exists(
            dtb,
            path,
            "non-removable",
        ),
        "bus_width": get_cells_text(
            dtb,
            path,
            "bus-width",
        ),
        "reg": get_cells_text(
            dtb,
            path,
            "reg",
        ),
        "phys": get_cells_text(
            dtb,
            path,
            "phys",
        ),
        "vmmc_supply": get_cells_text(
            dtb,
            path,
            "vmmc-supply",
        ),
        "vqmmc_supply": get_cells_text(
            dtb,
            path,
            "vqmmc-supply",
        ),
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dtb",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Backward-compatible active compatible node list",
    )

    parser.add_argument(
        "--graph-output",
        help="Optional complete active DT supplier graph",
    )

    args = parser.parse_args()

    all_nodes = list(walk_all(args.dtb))

    active_nodes = [
        node
        for node in all_nodes
        if node["available"]
    ]

    compatible_nodes = [
        compatible_node_record(args.dtb, node["path"])
        for node in active_nodes
        if compatibles(args.dtb, node["path"])
    ]

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(
        json.dumps(
            compatible_nodes,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Active compatible nodes: {len(compatible_nodes)}"
    )
    print(f"Output: {out}")

    if args.graph_output:
        all_node_map = {
            node["path"]: node
            for node in all_nodes
        }

        phandles = build_phandle_index(
            args.dtb,
            all_nodes,
        )

        graph_nodes = {}

        for node in active_nodes:
            path = node["path"]

            graph_nodes[path] = {
                "path": path,
                "status": node["status"],
                "compatible": compatibles(
                    args.dtb,
                    path,
                ),
                "phandle": None,
                "suppliers": node_suppliers(
                    args.dtb,
                    path,
                    phandles,
                    all_node_map,
                ),
            }

            for prop in ("phandle", "linux,phandle"):
                values = get_cells(
                    args.dtb,
                    path,
                    prop,
                )

                if values:
                    graph_nodes[path]["phandle"] = (
                        f"0x{values[0]:x}"
                    )
                    break

        graph = {
            "dtb": str(Path(args.dtb)),
            "active_node_count": len(active_nodes),
            "active_compatible_node_count": (
                len(compatible_nodes)
            ),
            "phandles": {
                f"0x{phandle:x}": path
                for phandle, path in sorted(
                    phandles.items()
                )
            },
            "nodes": graph_nodes,
        }

        graph_out = Path(args.graph_output)
        graph_out.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        graph_out.write_text(
            json.dumps(
                graph,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        supplier_count = sum(
            len(node["suppliers"])
            for node in graph_nodes.values()
        )

        unresolved_count = sum(
            1
            for node in graph_nodes.values()
            for supplier in node["suppliers"]
            if supplier.get("parse_error")
        )

        print(
            f"Active DT graph nodes: {len(graph_nodes)}"
        )
        print(
            f"Supplier edges:        {supplier_count}"
        )
        print(
            f"Supplier parse errors: {unresolved_count}"
        )
        print(f"Graph output:          {graph_out}")


if __name__ == "__main__":
    main()
