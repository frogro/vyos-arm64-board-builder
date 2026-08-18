#!/usr/bin/env python3

import argparse
import re
from collections import defaultdict
from pathlib import Path


OBJ_RE = re.compile(
    r'^\s*obj-\$\((CONFIG_[A-Za-z0-9_]+)\)\s*[:+]?=\s*(.*?)\s*$'
)

COMPOSITE_RE = re.compile(
    r'^\s*([A-Za-z0-9_.-]+)-(?:y|objs)\s*[:+]?=\s*(.*?)\s*$'
)

CELL_ARRAY_RE = re.compile(
    r'(?:static\s+)?(?:const\s+)?'
    r'struct\s+mfd_cell\s+'
    r'([A-Za-z0-9_]+)\s*\[\s*\]\s*=\s*'
    r'\{(.*?)\n\};',
    re.S,
)

CELL_NAME_RE = re.compile(
    r'\.name\s*=\s*"([^"]+)"'
)

PROBE_CALL_RE = re.compile(
    r'\b([A-Za-z_][A-Za-z0-9_]*probe)\s*'
    r'\((.*?)\)\s*;',
    re.S,
)

VARIANT_RE = re.compile(
    r'\b[A-Z][A-Z0-9_]*_ID\b'
)

DRIVER_NAME_RE = re.compile(
    r'\.name\s*=\s*"([^"]+)"'
)

MFD_ADD_RE = re.compile(
    r'\b(?:devm_)?mfd_add_devices\s*\((.*?)\)\s*;',
    re.S,
)


def read_active_mfd_sources(driver_map):
    result = set()

    with open(driver_map, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")

            if len(parts) < 3:
                continue

            source = parts[2].strip()

            if source.startswith("drivers/mfd/"):
                result.add(source)

    return result


def object_sources(makefile, object_name, lines):
    directory = makefile.parent
    result = set()

    if not object_name.endswith(".o"):
        return result

    direct = directory / (object_name[:-2] + ".c")

    if direct.is_file():
        result.add(direct)
        return result

    stem = object_name[:-2]

    for line in lines:
        match = COMPOSITE_RE.match(line)

        if not match or match.group(1) != stem:
            continue

        rhs = match.group(2).split("#", 1)[0]

        for token in rhs.split():
            if not token.endswith(".o"):
                continue

            source = directory / (token[:-2] + ".c")

            if source.is_file():
                result.add(source)

    return result


def build_source_config_map(kernel):
    result = defaultdict(set)

    for makefile in kernel.rglob("Makefile"):
        try:
            lines = makefile.read_text(
                encoding="utf-8",
                errors="ignore",
            ).splitlines()
        except OSError:
            continue

        for line in lines:
            match = OBJ_RE.match(line)

            if not match:
                continue

            config = match.group(1)
            rhs = match.group(2).split("#", 1)[0]

            for token in rhs.split():
                if not token.endswith(".o"):
                    continue

                for source in object_sources(
                    makefile,
                    token,
                    lines,
                ):
                    try:
                        relative = source.relative_to(kernel)
                    except ValueError:
                        continue

                    result[str(relative)].add(config)

    return result


def build_platform_driver_index(kernel):
    result = defaultdict(set)

    for root_name in ("drivers", "sound"):
        root = kernel / root_name

        if not root.is_dir():
            continue

        for source in root.rglob("*.c"):
            try:
                text = source.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )
            except OSError:
                continue

            if (
                "struct platform_driver" not in text
                and "platform_device_id" not in text
            ):
                continue

            for name in DRIVER_NAME_RE.findall(text):
                result[name].add(
                    str(source.relative_to(kernel))
                )

    return result


def parse_cell_arrays(text):
    result = {}

    for match in CELL_ARRAY_RE.finditer(text):
        array_name = match.group(1)
        body = match.group(2)

        result[array_name] = sorted(
            set(CELL_NAME_RE.findall(body))
        )

    return result


def direct_active_arrays(text, arrays):
    active = set()

    for call in MFD_ADD_RE.findall(text):
        for array_name in arrays:
            if re.search(
                r'\b' + re.escape(array_name) + r'\b',
                call,
            ):
                active.add(array_name)

    return active


def variants_from_active_source(text):
    result = set()

    for match in PROBE_CALL_RE.finditer(text):
        function = match.group(1)
        arguments = match.group(2)

        for variant in VARIANT_RE.findall(arguments):
            result.add((function, variant))

    return result


def arrays_for_variant(mfd_sources, variant):
    result = []

    case_re = re.compile(
        r'\bcase\s+'
        + re.escape(variant)
        + r'\s*:(.*?)'
          r'(?=\n\s*(?:case\b|default\s*:|\}))',
        re.S,
    )

    cells_re = re.compile(
        r'\bcells\s*=\s*([A-Za-z0-9_]+)\s*;'
    )

    for relative, text in mfd_sources.items():
        arrays = parse_cell_arrays(text)

        if not arrays:
            continue

        for match in case_re.finditer(text):
            cell_match = cells_re.search(
                match.group(1)
            )

            if not cell_match:
                continue

            array_name = cell_match.group(1)

            if array_name in arrays:
                result.append(
                    (
                        relative,
                        array_name,
                        arrays[array_name],
                    )
                )

    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Derive drivers for platform children created "
            "by active Linux MFD drivers"
        )
    )

    parser.add_argument("--kernel", required=True)
    parser.add_argument("--driver-map", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--unresolved")

    args = parser.parse_args()

    kernel = Path(args.kernel).resolve()
    driver_map = Path(args.driver_map)
    output = Path(args.output)

    active_sources = read_active_mfd_sources(
        driver_map
    )

    mfd_sources = {}

    mfd_root = kernel / "drivers/mfd"

    for source in mfd_root.rglob("*.c"):
        try:
            relative = str(
                source.relative_to(kernel)
            )

            mfd_sources[relative] = source.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        except OSError:
            continue

    active_cells = set()

    for parent_source in sorted(active_sources):
        text = mfd_sources.get(parent_source)

        if text is None:
            continue

        # Direct MFD cell arrays used by the active driver.
        arrays = parse_cell_arrays(text)

        for array_name in direct_active_arrays(
            text,
            arrays,
        ):
            for child in arrays[array_name]:
                active_cells.add(
                    (
                        parent_source,
                        "",
                        "",
                        parent_source,
                        array_name,
                        child,
                    )
                )

        # Variant-specific handoff to an MFD core.
        for function, variant in variants_from_active_source(
            text
        ):
            for core_source, array_name, children in (
                arrays_for_variant(
                    mfd_sources,
                    variant,
                )
            ):
                for child in children:
                    active_cells.add(
                        (
                            parent_source,
                            function,
                            variant,
                            core_source,
                            array_name,
                            child,
                        )
                    )

    print("Indexing Kbuild source mappings...", flush=True)
    source_configs = build_source_config_map(
        kernel
    )

    print("Indexing platform driver names...", flush=True)
    platform_index = build_platform_driver_index(
        kernel
    )

    rows = set()
    unresolved = set()

    for (
        parent_source,
        function,
        variant,
        core_source,
        array_name,
        child,
    ) in sorted(active_cells):

        child_sources = platform_index.get(
            child,
            set(),
        )

        mapped = False

        for child_source in sorted(child_sources):
            configs = source_configs.get(
                child_source,
                set(),
            )

            for config in sorted(configs):
                mapped = True

                origin = (
                    "mfd:"
                    + parent_source
                    + ":"
                    + child
                )

                rows.add(
                    (
                        origin,
                        config,
                        child_source,
                        variant or "-",
                        core_source,
                        array_name,
                    )
                )

        if not mapped:
            unresolved.add(
                (
                    parent_source,
                    variant or "-",
                    core_source,
                    array_name,
                    child,
                )
            )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output.open("w", encoding="utf-8") as f:
        for row in sorted(rows):
            f.write("\t".join(row) + "\n")

    unresolved_path = (
        Path(args.unresolved)
        if args.unresolved
        else output.with_suffix(
            output.suffix + ".unresolved"
        )
    )

    with unresolved_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        for row in sorted(unresolved):
            f.write("\t".join(row) + "\n")

    print()
    print("Generic active MFD child derivation")
    print("-----------------------------------")
    print(f"Active MFD sources:       {len(active_sources)}")
    print(f"Active MFD child cells:   {len(active_cells)}")
    print(f"Resolved child mappings:  {len(rows)}")
    print(f"Unresolved child names:   {len(unresolved)}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
