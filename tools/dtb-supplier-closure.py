#!/usr/bin/env python3

import argparse
import json
from collections import deque
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def edge_key(edge):
    return (
        edge.get("consumer"),
        edge.get("property"),
        edge.get("phandle"),
        tuple(edge.get("args", [])),
        edge.get("target_path"),
        edge.get("provider_path"),
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve the recursive DT supplier closure starting "
            "from one or more active DT root nodes."
        )
    )

    parser.add_argument(
        "--graph",
        required=True,
        help="supplier-graph.json from dtb-active-nodes.py",
    )

    parser.add_argument(
        "--root-node",
        action="append",
        required=True,
        help=(
            "Active DT node from which supplier traversal starts. "
            "May be specified multiple times."
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    args = parser.parse_args()

    graph = load_json(args.graph)
    graph_nodes = graph.get("nodes", {})

    roots = []

    for path in args.root_node:
        if path not in graph_nodes:
            raise SystemExit(
                f"ERROR: root node is not in active DT graph: {path}"
            )

        if path not in roots:
            roots.append(path)

    queue = deque(roots)
    queued = set(roots)
    visited = set()

    closure_edges = []
    seen_edges = set()

    while queue:
        consumer = queue.popleft()
        visited.add(consumer)

        node = graph_nodes[consumer]

        for supplier in node.get("suppliers", []):
            edge = dict(supplier)
            edge["consumer"] = consumer

            key = edge_key(edge)

            if key not in seen_edges:
                seen_edges.add(key)
                closure_edges.append(edge)

            #
            # target_path is important for non-compatible child
            # nodes such as regulator or pinctrl state nodes.
            #
            # provider_path is the nearest compatible DT ancestor
            # and therefore normally the node which maps to a
            # Linux DT driver.
            #
            # Traverse both. This preserves child-specific supplier
            # relationships without walking down into unrelated
            # siblings of an MFD/provider device.
            #
            for candidate in (
                supplier.get("target_path"),
                supplier.get("provider_path"),
            ):
                if not candidate:
                    continue

                if candidate not in graph_nodes:
                    raise SystemExit(
                        "ERROR: supplier target/provider missing "
                        f"from active graph: {candidate}"
                    )

                if candidate not in visited and candidate not in queued:
                    queue.append(candidate)
                    queued.add(candidate)

    closure_nodes = {}

    for path in sorted(visited):
        source = graph_nodes[path]

        closure_nodes[path] = {
            "path": path,
            "status": source.get("status"),
            "compatible": source.get("compatible", []),
            "phandle": source.get("phandle"),
        }

    closure_edges.sort(
        key=lambda edge: (
            edge["consumer"],
            edge.get("property") or "",
            edge.get("phandle") or "",
            tuple(edge.get("args", [])),
            edge.get("target_path") or "",
            edge.get("provider_path") or "",
        )
    )

    output = {
        "schema_version": 1,
        "source_graph": str(Path(args.graph)),
        "roots": roots,
        "node_count": len(closure_nodes),
        "edge_count": len(closure_edges),
        "nodes": closure_nodes,
        "edges": closure_edges,
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    out.write_text(
        json.dumps(
            output,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("DT supplier closure")
    print("-------------------")
    print(f"Roots: {len(roots)}")

    for root in roots:
        print(f"  {root}")

    print(f"Closure nodes: {len(closure_nodes)}")
    print(f"Closure edges: {len(closure_edges)}")
    print(f"Output:        {out}")


if __name__ == "__main__":
    main()
