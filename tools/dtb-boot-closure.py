#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd):
    subprocess.run(
        cmd,
        check=True,
    )


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve DT boot supplier closure to a fixed point. "
            "Driver transport dependencies discovered during one "
            "iteration become roots of the next iteration."
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
        "--driver-map",
        required=True,
    )

    parser.add_argument(
        "--root-node",
        action="append",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        required=True,
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=16,
    )

    args = parser.parse_args()

    here = Path(__file__).resolve().parent

    supplier_tool = (
        here /
        "dtb-supplier-closure.py"
    )

    context_tool = (
        here /
        "dtb-driver-context.py"
    )

    outdir = Path(args.output_dir)

    workdir = (
        outdir /
        "iterations"
    )

    if outdir.exists():
        shutil.rmtree(outdir)

    workdir.mkdir(
        parents=True,
        exist_ok=True,
    )

    roots = []

    for root in args.root_node:
        if root not in roots:
            roots.append(root)

    history = []

    final_closure = None
    final_context = None

    for iteration in range(
        1,
        args.max_iterations + 1,
    ):
        idir = (
            workdir /
            f"{iteration:02d}"
        )

        idir.mkdir(
            parents=True,
            exist_ok=True,
        )

        closure_path = (
            idir /
            "supplier-closure.json"
        )

        context_dir = (
            idir /
            "driver-context"
        )

        closure_cmd = [
            sys.executable,
            str(supplier_tool),
            "--graph",
            args.graph,
        ]

        for root in roots:
            closure_cmd.extend(
                [
                    "--root-node",
                    root,
                ]
            )

        closure_cmd.extend(
            [
                "--output",
                str(closure_path),
            ]
        )

        print()
        print(
            f"===== BOOT CLOSURE ITERATION "
            f"{iteration} ====="
        )
        print(
            "Roots:"
        )

        for root in roots:
            print(
                f"  {root}"
            )

        run(closure_cmd)

        run(
            [
                sys.executable,
                str(context_tool),
                "--kernel",
                args.kernel,
                "--graph",
                args.graph,
                "--closure",
                str(closure_path),
                "--driver-map",
                args.driver_map,
                "--output-dir",
                str(context_dir),
            ]
        )

        context_path = (
            context_dir /
            "driver-context.json"
        )

        closure = load_json(
            closure_path
        )

        context = load_json(
            context_path
        )

        discovered = list(
            context.get(
                "bus_provider_roots",
                [],
            )
        )

        new_roots = [
            root
            for root in discovered
            if root not in roots
        ]

        history.append(
            {
                "iteration": iteration,
                "roots": list(roots),
                "closure_nodes": (
                    closure["node_count"]
                ),
                "closure_edges": (
                    closure["edge_count"]
                ),
                "resolved_drivers": (
                    context[
                        "resolved_count"
                    ]
                ),
                "unresolved_drivers": (
                    context[
                        "unresolved_count"
                    ]
                ),
                "discovered_bus_roots": (
                    discovered
                ),
                "new_bus_roots": (
                    new_roots
                ),
            }
        )

        print()
        print(
            f"Iteration {iteration}:"
        )
        print(
            f"  closure nodes: "
            f"{closure['node_count']}"
        )
        print(
            f"  closure edges: "
            f"{closure['edge_count']}"
        )
        print(
            f"  resolved drivers: "
            f"{context['resolved_count']}"
        )
        print(
            f"  unresolved drivers: "
            f"{context['unresolved_count']}"
        )
        print(
            f"  discovered bus roots: "
            f"{len(discovered)}"
        )
        print(
            f"  new bus roots: "
            f"{len(new_roots)}"
        )

        for root in new_roots:
            print(
                f"    + {root}"
            )

        final_closure = closure_path
        final_context = context_path

        if not new_roots:
            break

        roots.extend(
            new_roots
        )

    else:
        raise SystemExit(
            "ERROR: DT boot closure did not "
            f"converge after "
            f"{args.max_iterations} iterations"
        )

    final_dir = (
        outdir /
        "final"
    )

    final_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_closure_out = (
        final_dir /
        "supplier-closure.json"
    )

    final_context_out = (
        final_dir /
        "driver-context.json"
    )

    shutil.copy2(
        final_closure,
        final_closure_out,
    )

    shutil.copy2(
        final_context,
        final_context_out,
    )

    #
    # Preserve the human-readable derived maps from
    # the final driver-context iteration as well.
    #
    final_context_dir = (
        final_context.parent
    )

    for name in (
        "resolved-config-map.tsv",
        "bus-provider-roots.txt",
        "unresolved-driver-context.json",
    ):
        source = (
            final_context_dir /
            name
        )

        if source.exists():
            shutil.copy2(
                source,
                final_dir / name,
            )

    summary = {
        "schema_version": 1,
        "initial_roots": list(
            args.root_node
        ),
        "final_roots": roots,
        "iterations": len(
            history
        ),
        "history": history,
        "final_supplier_closure": str(
            final_closure_out
        ),
        "final_driver_context": str(
            final_context_out
        ),
    }

    summary_out = (
        outdir /
        "boot-closure-summary.json"
    )

    summary_out.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    final_closure_data = load_json(
        final_closure_out
    )

    final_context_data = load_json(
        final_context_out
    )

    print()
    print("DT boot closure fixed point")
    print("---------------------------")
    print(
        f"Iterations:       "
        f"{len(history)}"
    )
    print(
        f"Initial roots:    "
        f"{len(args.root_node)}"
    )
    print(
        f"Final roots:      "
        f"{len(roots)}"
    )
    print(
        f"Closure nodes:    "
        f"{final_closure_data['node_count']}"
    )
    print(
        f"Closure edges:    "
        f"{final_closure_data['edge_count']}"
    )
    print(
        f"Resolved drivers: "
        f"{final_context_data['resolved_count']}"
    )
    print(
        f"Unresolved:       "
        f"{final_context_data['unresolved_count']}"
    )

    print()
    print("Final roots:")

    for root in roots:
        print(
            f"  {root}"
        )

    print()
    print(
        f"Closure: {final_closure_out}"
    )
    print(
        f"Context: {final_context_out}"
    )
    print(
        f"Summary: {summary_out}"
    )


if __name__ == "__main__":
    main()
