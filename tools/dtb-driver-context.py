#!/usr/bin/env python3

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path


DEVICE_BUS_PATTERNS = {
    "spi": (
        r"\bstruct\s+spi_driver\b",
        r"\bmodule_spi_driver\s*\(",
    ),
    "i2c": (
        r"\bstruct\s+i2c_driver\b",
        r"\bmodule_i2c_driver\s*\(",
    ),
    "amba": (
        r"\bstruct\s+amba_driver\b",
        r"\bmodule_amba_driver\s*\(",
    ),
}


BUS_PROVIDER_PATTERNS = {
    "spi": (
        r"\bspi_register_controller\s*\(",
        r"\bdevm_spi_register_controller\s*\(",
        r"\bspi_register_master\s*\(",
        r"\bdevm_spi_register_master\s*\(",
        r"\bspi_alloc_host\s*\(",
        r"\bspi_alloc_master\s*\(",
    ),
    "i2c": (
        r"\bi2c_add_adapter\s*\(",
        r"\bi2c_add_numbered_adapter\s*\(",
        r"\bdevm_i2c_add_adapter\s*\(",
    ),
}


ATTR = r"__[A-Za-z0-9_]+(?:\s*\([^)]*\))?"

OF_TABLE_RE = re.compile(
    rf"""
    struct\s+of_device_id\s+
    (?:(?:{ATTR})\s+)*
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*
    \[\s*\]\s*
    (?:(?:{ATTR})\s*)*
    =\s*\{{
    (?P<body>.*?)
    \n\s*\}};
    """,
    re.S | re.X,
)

OF_COMPAT_RE = re.compile(
    r'\.compatible\s*=\s*"([^"]+)"'
)

OF_MATCH_REF_RE = re.compile(
    r"""
    \.of_match_table\s*=\s*
    (?:
        of_match_ptr\s*\(\s*
    )?
    &?
    (?P<name>[A-Za-z_][A-Za-z0-9_]*)
    """,
    re.X,
)


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_driver_map(path):
    mapping = defaultdict(list)

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

            if row not in mapping[compatible]:
                mapping[compatible].append(row)

    return mapping


def normalize(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower(),
    )


def parent_path(path):
    if path == "/":
        return None

    parent = path.rsplit("/", 1)[0]

    return parent or "/"


def ancestors(path):
    current = parent_path(path)

    while current:
        yield current

        if current == "/":
            break

        current = parent_path(current)


class SourceInspector:
    def __init__(self, kernel):
        self.kernel = Path(kernel)

        self.text_cache = {}
        self.of_cache = {}
        self.config_cache = {}
        self.basename_index = None

    def text(self, source):
        if source not in self.text_cache:
            path = self.kernel / source

            try:
                self.text_cache[source] = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                self.text_cache[source] = ""

        return self.text_cache[source]

    def classify(self, source, patterns):
        text = self.text(source)
        found = set()

        for kind, regexes in patterns.items():
            if any(
                re.search(regex, text)
                for regex in regexes
            ):
                found.add(kind)

        return found

    def device_buses(self, source):
        return self.classify(
            source,
            DEVICE_BUS_PATTERNS,
        )

    def provided_buses(self, source):
        return self.classify(
            source,
            BUS_PROVIDER_PATTERNS,
        )

    def of_driver_bound_compatibles(self, source):
        if source in self.of_cache:
            return self.of_cache[source]

        text = self.text(source)

        tables = {}

        for match in OF_TABLE_RE.finditer(text):
            name = match.group("name")

            tables[name] = set(
                OF_COMPAT_RE.findall(
                    match.group("body")
                )
            )

        references = {
            match.group("name")
            for match in OF_MATCH_REF_RE.finditer(text)
        }

        compatibles = set()

        for name in references:
            compatibles.update(
                tables.get(name, set())
            )

        result = {
            "tables": tables,
            "references": references,
            "compatibles": compatibles,
        }

        self.of_cache[source] = result

        return result

    def is_of_driver_bound(self, source, compatible):
        return (
            compatible
            in self.of_driver_bound_compatibles(
                source
            )["compatibles"]
        )

    def configs_for_source(self, source):
        if source in self.config_cache:
            return self.config_cache[source]

        source_path = self.kernel / source
        makefile = source_path.parent / "Makefile"

        if not makefile.is_file():
            self.config_cache[source] = []
            return []

        text = makefile.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        obj = source_path.stem + ".o"

        configs = set()

        #
        # Direct Kbuild mapping:
        #
        # obj-$(CONFIG_FOO) += foo.o
        #
        for line in text.splitlines():
            if obj not in line:
                continue

            configs.update(
                re.findall(
                    r"CONFIG_[A-Za-z0-9_]+",
                    line,
                )
            )

        #
        # One-level composite object:
        #
        # foo-y += foo_core.o
        # obj-$(CONFIG_FOO) += foo.o
        #
        parent_objects = set()

        for line in text.splitlines():
            if obj not in line:
                continue

            match = re.match(
                r"""
                \s*
                (?P<name>[A-Za-z0-9_.-]+)
                -(?:y|objs)
                \s*[:+]?=
                """,
                line,
                re.X,
            )

            if match:
                parent_objects.add(
                    match.group("name") + ".o"
                )

        for parent_obj in parent_objects:
            for line in text.splitlines():
                if parent_obj not in line:
                    continue

                configs.update(
                    re.findall(
                        r"CONFIG_[A-Za-z0-9_]+",
                        line,
                    )
                )

        result = sorted(configs)

        self.config_cache[source] = result

        return result

    def build_basename_index(self):
        if self.basename_index is not None:
            return

        index = defaultdict(list)

        drivers = self.kernel / "drivers"

        for path in drivers.rglob("*.c"):
            rel = path.relative_to(
                self.kernel
            ).as_posix()

            index[
                normalize(path.stem)
            ].append(rel)

        self.basename_index = index

    def sources_for_basename(self, token):
        self.build_basename_index()

        return sorted(
            set(
                self.basename_index.get(
                    normalize(token),
                    [],
                )
            )
        )


def candidates_for_node(node, mapping):
    result = {}

    for compatible in node.get(
        "compatible",
        [],
    ):
        for row in mapping.get(
            compatible,
            [],
        ):
            key = (
                row["config"],
                row["source"],
            )

            result.setdefault(
                key,
                {
                    "config": row["config"],
                    "source": row["source"],
                    "compatibles": [],
                },
            )

            if (
                compatible
                not in result[key]["compatibles"]
            ):
                result[key][
                    "compatibles"
                ].append(compatible)

    return list(result.values())


def add_candidate_metadata(
    candidate,
    inspector,
):
    result = dict(candidate)

    result["device_buses"] = sorted(
        inspector.device_buses(
            candidate["source"]
        )
    )

    result["of_driver_bound"] = any(
        inspector.is_of_driver_bound(
            candidate["source"],
            compatible,
        )
        for compatible
        in candidate["compatibles"]
    )

    return result


def prefer_driver_bound(candidates):
    bound = [
        candidate
        for candidate in candidates
        if candidate.get("of_driver_bound")
    ]

    #
    # Conservative policy:
    #
    # If at least one conventional driver-bound OF
    # candidate exists, internal helper match tables
    # are discarded.
    #
    # If none exists, keep all legacy mapper rows so
    # SCMI/syscon/etc. are not accidentally lost.
    #
    if bound:
        return bound, "driver-bound"

    return candidates, "legacy-fallback"


def primecell_amba_fallback(
    node,
    inspector,
):
    compatibles = node.get(
        "compatible",
        [],
    )

    if "arm,primecell" not in compatibles:
        return []

    matches = {}

    for compatible in compatibles:
        if compatible == "arm,primecell":
            continue

        token = compatible.split(",", 1)[-1]

        sources = inspector.sources_for_basename(
            token
        )

        #
        # Strict fallback only:
        #
        # compatible device token must map to exactly
        # one normalized source basename.
        #
        if len(sources) != 1:
            continue

        source = sources[0]

        if (
            "amba"
            not in inspector.device_buses(
                source
            )
        ):
            continue

        configs = inspector.configs_for_source(
            source
        )

        #
        # Kbuild must also map that source to exactly
        # one CONFIG symbol.
        #
        if len(configs) != 1:
            continue

        config = configs[0]

        key = (
            config,
            source,
        )

        matches[key] = {
            "config": config,
            "source": source,
            "compatibles": [compatible],
            "device_buses": ["amba"],
            "of_driver_bound": False,
            "fallback": "primecell-amba-basename",
        }

    return list(matches.values())


def provider_bus_for_node(
    path,
    graph_nodes,
    mapping,
    inspector,
):
    for ancestor in ancestors(path):
        node = graph_nodes.get(ancestor)

        if not node:
            continue

        raw_candidates = candidates_for_node(
            node,
            mapping,
        )

        candidates = [
            add_candidate_metadata(
                candidate,
                inspector,
            )
            for candidate in raw_candidates
        ]

        candidates, _ = prefer_driver_bound(
            candidates
        )

        provider_buses = defaultdict(list)

        for candidate in candidates:
            buses = inspector.provided_buses(
                candidate["source"]
            )

            for bus in buses:
                provider_buses[bus].append(
                    candidate
                )

        #
        # Only accept an ancestor when Linux source
        # analysis identifies exactly one bus type.
        #
        if len(provider_buses) == 1:
            bus = next(iter(provider_buses))

            return {
                "path": ancestor,
                "bus": bus,
                "drivers": provider_buses[bus],
            }

    return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve DT compatible driver ambiguity "
            "using OF driver binding, Linux bus "
            "context and strict PrimeCell/AMBA "
            "fallbacks."
        )
    )

    parser.add_argument(
        "--kernel",
        required=True,
    )

    parser.add_argument(
        "--graph",
        required=True,
    )

    parser.add_argument(
        "--closure",
        required=True,
    )

    parser.add_argument(
        "--driver-map",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    args = parser.parse_args()

    graph = load_json(args.graph)
    closure = load_json(args.closure)
    mapping = load_driver_map(
        args.driver_map
    )

    graph_nodes = graph["nodes"]
    closure_nodes = closure["nodes"]

    inspector = SourceInspector(
        args.kernel
    )

    resolved = []
    unresolved = []
    bus_roots = set()

    for path in sorted(closure_nodes):
        node = graph_nodes.get(path)

        if not node:
            unresolved.append({
                "path": path,
                "reason": (
                    "missing-from-source-graph"
                ),
                "candidates": [],
            })
            continue

        if not node.get("compatible"):
            continue

        raw_candidates = candidates_for_node(
            node,
            mapping,
        )

        candidates = [
            add_candidate_metadata(
                candidate,
                inspector,
            )
            for candidate in raw_candidates
        ]

        raw_candidate_count = len(candidates)

        candidates, candidate_filter = (
            prefer_driver_bound(
                candidates
            )
        )

        #
        # OF mapping can legitimately be absent for
        # PrimeCell/AMBA devices. In that case use a
        # deliberately strict fallback:
        #
        # compatible token -> unique source basename
        #                    -> amba_driver
        #                    -> unique Kbuild CONFIG
        #
        if not candidates:
            amba = primecell_amba_fallback(
                node,
                inspector,
            )

            if len(amba) == 1:
                resolved.append({
                    "path": path,
                    "provider": None,
                    "selected": amba[0],
                    "raw_candidate_count": 0,
                    "candidate_count": 1,
                    "candidate_filter": (
                        "primecell-amba"
                    ),
                    "resolution": (
                        "primecell-amba-basename"
                    ),
                })
                continue

            if len(amba) > 1:
                unresolved.append({
                    "path": path,
                    "reason": (
                        "ambiguous-primecell-amba"
                    ),
                    "provider": None,
                    "candidates": amba,
                })
                continue

            unresolved.append({
                "path": path,
                "reason": "no-driver-candidate",
                "candidates": [],
            })
            continue

        provider = provider_bus_for_node(
            path,
            graph_nodes,
            mapping,
            inspector,
        )

        #
        # Driver-bound filtering may itself make an
        # otherwise ambiguous compatible unique.
        #
        if len(candidates) == 1:
            selected = candidates[0]

            device_buses = set(
                selected["device_buses"]
            )

            if (
                provider
                and provider["bus"]
                in device_buses
            ):
                bus_roots.add(
                    provider["path"]
                )

            if raw_candidate_count > 1:
                resolution = (
                    "driver-bound-preference"
                )
            else:
                resolution = "unique"

            resolved.append({
                "path": path,
                "provider": provider,
                "selected": selected,
                "raw_candidate_count": (
                    raw_candidate_count
                ),
                "candidate_count": 1,
                "candidate_filter": (
                    candidate_filter
                ),
                "resolution": resolution,
            })
            continue

        #
        # Multiple real OF drivers remain. Resolve
        # only if the parent controller identifies
        # one transport bus and exactly one driver
        # binds to that bus.
        #
        if provider:
            bus = provider["bus"]

            matching = [
                candidate
                for candidate in candidates
                if (
                    bus
                    in candidate["device_buses"]
                )
            ]

            if len(matching) == 1:
                bus_roots.add(
                    provider["path"]
                )

                resolved.append({
                    "path": path,
                    "provider": provider,
                    "selected": matching[0],
                    "raw_candidate_count": (
                        raw_candidate_count
                    ),
                    "candidate_count": (
                        len(candidates)
                    ),
                    "candidate_filter": (
                        candidate_filter
                    ),
                    "resolution": (
                        f"parent-bus:{bus}"
                    ),
                })
                continue

        unresolved.append({
            "path": path,
            "reason": (
                "ambiguous-driver-candidates"
            ),
            "provider": provider,
            "raw_candidate_count": (
                raw_candidate_count
            ),
            "candidate_filter": (
                candidate_filter
            ),
            "candidates": candidates,
        })

    outdir = Path(args.output_dir)

    outdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = {
        "schema_version": 2,
        "source_graph": str(
            Path(args.graph)
        ),
        "source_closure": str(
            Path(args.closure)
        ),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "bus_provider_roots": sorted(
            bus_roots
        ),
        "resolved": resolved,
        "unresolved": unresolved,
    }

    json_out = (
        outdir /
        "driver-context.json"
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
        "resolved-config-map.tsv"
    )

    with map_out.open(
        "w",
        encoding="utf-8",
    ) as f:
        for item in sorted(
            resolved,
            key=lambda x: x["path"],
        ):
            selected = item["selected"]

            provider = item.get(
                "provider"
            )

            provider_path = (
                provider["path"]
                if provider
                else "-"
            )

            provider_bus = (
                provider["bus"]
                if provider
                else "-"
            )

            print(
                item["path"],
                ",".join(
                    selected[
                        "compatibles"
                    ]
                ),
                selected["config"],
                selected["source"],
                ",".join(
                    selected[
                        "device_buses"
                    ]
                ) or "-",
                provider_bus,
                provider_path,
                item["resolution"],
                sep="\t",
                file=f,
            )

    roots_out = (
        outdir /
        "bus-provider-roots.txt"
    )

    roots_out.write_text(
        "".join(
            f"{path}\n"
            for path in sorted(
                bus_roots
            )
        ),
        encoding="utf-8",
    )

    unresolved_out = (
        outdir /
        "unresolved-driver-context.json"
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

    print("DT driver context")
    print("-----------------")

    print(
        "Closure compatible nodes: "
        f"{sum(1 for n in closure_nodes.values() if n.get('compatible'))}"
    )

    print(
        f"Resolved nodes:            "
        f"{len(resolved)}"
    )

    print(
        f"Unresolved nodes:          "
        f"{len(unresolved)}"
    )

    print(
        f"Additional bus roots:      "
        f"{len(bus_roots)}"
    )

    for root in sorted(bus_roots):
        print(f"  {root}")

    print(f"Context: {json_out}")
    print(f"Map:     {map_out}")
    print(f"Roots:   {roots_out}")


if __name__ == "__main__":
    main()
