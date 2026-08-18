#!/usr/bin/env python3

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Combine resolved DT boot drivers and required "
            "MFD child services into one explicit boot-critical "
            "Kconfig symbol set."
        )
    )

    parser.add_argument(
        "--driver-context",
        required=True,
    )

    parser.add_argument(
        "--mfd-services",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    args = parser.parse_args()

    driver_context = load_json(
        args.driver_context
    )

    mfd_services = load_json(
        args.mfd_services
    )

    #
    # A boot-critical symbol set must never silently
    # proceed from an incomplete hardware resolution.
    #
    driver_unresolved = int(
        driver_context.get(
            "unresolved_count",
            0,
        )
    )

    mfd_unresolved = int(
        mfd_services.get(
            "unresolved_edge_count",
            0,
        )
    )

    if driver_unresolved:
        raise SystemExit(
            "ERROR: driver context still contains "
            f"{driver_unresolved} unresolved node(s)"
        )

    if mfd_unresolved:
        raise SystemExit(
            "ERROR: MFD service context still contains "
            f"{mfd_unresolved} unresolved edge(s)"
        )

    evidence = defaultdict(list)

    #
    # Every resolved node in the final supplier closure
    # is part of the path needed to reach the selected
    # boot medium. Therefore its resolved driver symbol
    # is boot-critical.
    #
    for item in driver_context.get(
        "resolved",
        [],
    ):
        selected = item.get(
            "selected",
            {},
        )

        symbol = selected.get(
            "config"
        )

        if not (
            symbol
            and symbol.startswith("CONFIG_")
        ):
            raise SystemExit(
                "ERROR: resolved driver has no valid "
                f"CONFIG symbol: {item.get('path')}"
            )

        evidence[symbol].append(
            {
                "kind": "dt-driver",
                "path": item.get(
                    "path"
                ),
                "source": selected.get(
                    "source"
                ),
                "resolution": item.get(
                    "resolution"
                ),
            }
        )

    #
    # MFD child devices are not necessarily represented
    # by their own DT compatible. Required services such
    # as regulators and pinctrl are therefore added from
    # the explicit service resolver.
    #
    for item in mfd_services.get(
        "resolved",
        [],
    ):
        symbol = item.get(
            "config"
        )

        if not (
            symbol
            and symbol.startswith("CONFIG_")
        ):
            raise SystemExit(
                "ERROR: resolved MFD service has no "
                "valid CONFIG symbol"
            )

        evidence[symbol].append(
            {
                "kind": "mfd-service",
                "service": item.get(
                    "service"
                ),
                "property": item.get(
                    "property"
                ),
                "consumer": item.get(
                    "consumer"
                ),
                "provider": item.get(
                    "provider_path"
                ),
                "source": item.get(
                    "child_source"
                ),
            }
        )

    symbols = sorted(
        evidence
    )

    outdir = Path(
        args.output_dir
    )

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    symbols_out = (
        outdir /
        "boot-critical-symbols.txt"
    )

    symbols_out.write_text(
        "".join(
            f"{symbol}\n"
            for symbol in symbols
        ),
        encoding="utf-8",
    )

    map_out = (
        outdir /
        "boot-critical-config-map.tsv"
    )

    with map_out.open(
        "w",
        encoding="utf-8",
    ) as f:
        for symbol in symbols:
            kinds = sorted(
                {
                    item["kind"]
                    for item
                    in evidence[symbol]
                }
            )

            sources = sorted(
                {
                    item.get(
                        "source"
                    )
                    for item
                    in evidence[symbol]
                    if item.get(
                        "source"
                    )
                }
            )

            print(
                "boot-critical",
                symbol,
                ",".join(kinds),
                ",".join(sources),
                sep="\t",
                file=f,
            )

    json_out = (
        outdir /
        "boot-critical-symbols.json"
    )

    json_out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_driver_context": str(
                    Path(
                        args.driver_context
                    )
                ),
                "source_mfd_services": str(
                    Path(
                        args.mfd_services
                    )
                ),
                "symbol_count": len(
                    symbols
                ),
                "symbols": symbols,
                "evidence": {
                    symbol: evidence[
                        symbol
                    ]
                    for symbol
                    in symbols
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "DT boot-critical symbols"
    )
    print(
        "------------------------"
    )
    print(
        f"Driver nodes: "
        f"{driver_context.get('resolved_count', 0)}"
    )
    print(
        f"MFD service edges: "
        f"{mfd_services.get('resolved_edge_count', 0)}"
    )
    print(
        f"Unique CONFIG symbols: "
        f"{len(symbols)}"
    )

    for symbol in symbols:
        kinds = sorted(
            {
                item["kind"]
                for item
                in evidence[symbol]
            }
        )

        print(
            f"  {symbol} "
            f"[{','.join(kinds)}]"
        )

    print(
        f"Symbols: {symbols_out}"
    )
    print(
        f"Map:     {map_out}"
    )
    print(
        f"Context: {json_out}"
    )


if __name__ == "__main__":
    main()
