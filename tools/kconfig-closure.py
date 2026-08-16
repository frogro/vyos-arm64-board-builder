#!/usr/bin/env python3

import argparse
import re
from pathlib import Path


CONFIG_RE = re.compile(
    r'^(?:config|menuconfig)\s+([A-Za-z0-9_]+)\s*$'
)

DEPENDS_RE = re.compile(
    r'^\s*depends\s+on\s+(.+?)\s*$'
)

SELECT_RE = re.compile(
    r'^\s*select\s+([A-Za-z0-9_]+)(?:\s+if\s+(.+))?\s*$'
)

#
# Structural Kconfig "if"/"endif" directives are parsed only when they
# start at column 0.  Indented text may belong to a help block, e.g.
# "if unsure, say N.", and must never become a Kconfig dependency.
#
IF_RE = re.compile(
    r'^if\s+(.+?)\s*$'
)

ENDIF_RE = re.compile(
    r'^endif(?:\s*#.*)?$'
)

MENU_RE = re.compile(
    r'^menu\s+"'
)

ENDMENU_RE = re.compile(
    r'^endmenu(?:\s*#.*)?$'
)

COMMENT_RE = re.compile(
    r'^comment\s+"'
)

CHOICE_RE = re.compile(
    r'^choice(?:\s+.*)?$'
)

ENDCHOICE_RE = re.compile(
    r'^endchoice(?:\s*#.*)?$'
)

SOURCE_RE = re.compile(
    r'^(?:source|rsource|osource|orsource)\s+'
)

PROMPT_RE = re.compile(
    r'^\s*(?:bool|tristate|string|int|hex)\s+"'
)

SYMBOL_RE = re.compile(
    r'\b[A-Z][A-Z0-9_]+\b'
)


def read_config(path):
    result = {}

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            m = re.match(
                r'^(CONFIG_[A-Za-z0-9_]+)=(.*)$',
                line
            )
            if m:
                result[m.group(1).removeprefix("CONFIG_")] = m.group(2)
                continue

            m = re.match(
                r'^# (CONFIG_[A-Za-z0-9_]+) is not set$',
                line
            )
            if m:
                result[m.group(1).removeprefix("CONFIG_")] = "n"

    return result


def scan_kconfig(kernel):
    defs = {}
    reverse_select = {}

    kernel_path = Path(kernel)

    #
    # Kconfig source files inherit structural "if" conditions from the
    # point at which they are sourced.  Since this scanner parses files
    # individually, collect those source-site conditions first and apply
    # them when parsing the sourced file.
    #
    #
    # Build the Kconfig source graph first.
    #
    # An edge records the local structural if-context around a source:
    #
    #   parent --[local ifs]--> child
    #
    # These conditions must be propagated transitively.  Example:
    #
    #   drivers/mtd/Kconfig
    #       if MTD
    #           source "drivers/mtd/nand/Kconfig"
    #
    #   drivers/mtd/nand/Kconfig
    #           source "drivers/mtd/nand/spi/Kconfig"
    #
    # CONFIG symbols in nand/spi/Kconfig therefore inherit MTD even
    # though their immediate source statement has no local "if MTD".
    #
    source_edges = []

    for parent in kernel_path.rglob("Kconfig*"):
        if not parent.is_file():
            continue

        rel_parent = parent.relative_to(kernel_path)

        if (
            len(rel_parent.parts) >= 2
            and rel_parent.parts[0] == "arch"
            and rel_parent.parts[1] == "arm"
        ):
            continue

        try:
            parent_lines = parent.read_text(
                encoding="utf-8",
                errors="ignore"
            ).splitlines()
        except OSError:
            continue

        local_if_stack = []

        for parent_line in parent_lines:
            m = IF_RE.match(parent_line)

            if m:
                local_if_stack.append(m.group(1))
                continue

            if ENDIF_RE.match(parent_line):
                if local_if_stack:
                    local_if_stack.pop()
                continue

            m = re.match(
                r'^source\s+"([^"]+)"\s*$',
                parent_line
            )

            if not m:
                continue

            source_name = m.group(1)

            #
            # Variable-expanded source paths cannot be resolved here
            # without evaluating the complete Kconfig environment.
            #
            if "$" in source_name:
                continue

            target = kernel_path / source_name

            try:
                target_rel = (
                    target.resolve()
                    .relative_to(kernel_path.resolve())
                    .as_posix()
                )
            except (OSError, ValueError):
                continue

            source_edges.append(
                (
                    rel_parent.as_posix(),
                    target_rel,
                    tuple(local_if_stack),
                )
            )

    #
    # Determine roots of the resolvable source graph.  A root starts
    # with an empty inherited context.  Contexts then flow through all
    # source edges until a fixed point is reached.
    #
    #
    # Kconfig has one real entry point: the top-level Kconfig.
    #
    # Treating every apparently unsourced Kconfig file as an
    # independent root creates false empty contexts and can erase
    # inherited conditions from the real source graph.
    #
    source_if_context = {
        "Kconfig": [tuple()]
    }

    changed = True

    while changed:
        changed = False

        for parent, target, local_context in source_edges:
            parent_contexts = source_if_context.get(
                parent,
                []
            )

            if not parent_contexts:
                continue

            for parent_context in parent_contexts:
                combined = tuple(
                    dict.fromkeys(
                        parent_context + local_context
                    )
                )

                contexts = source_if_context.setdefault(
                    target,
                    []
                )

                if combined not in contexts:
                    contexts.append(combined)
                    changed = True

    for path in kernel_path.rglob("Kconfig*"):
        if not path.is_file():
            continue

        rel = path.relative_to(kernel_path)

        #
        # This resolver currently targets ARM64 kernels.
        # Ignore ARM32-only Kconfig trees, otherwise symbols with
        # definitions in both arch/arm and arch/arm64 get their
        # dependencies incorrectly merged.
        #
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

        inherited_if_contexts = source_if_context.get(
            rel.as_posix(),
            []
        )

        #
        # Most Kconfig files have one structural source site.  If the
        # same file is sourced from multiple contexts, keep only
        # conditions common to every source site; adding a condition
        # which applies at only one source site would over-constrain the
        # symbol.
        #
        inherited_ifs = []

        if inherited_if_contexts:
            inherited_ifs = list(inherited_if_contexts[0])

            for context in inherited_if_contexts[1:]:
                inherited_ifs = [
                    expr
                    for expr in inherited_ifs
                    if expr in context
                ]

        if_stack = list(inherited_ifs)
        menu_stack = []
        current = None

        #
        # True only directly after a "menu" statement while parsing
        # properties belonging to that menu header.  This prevents a
        # later "comment ... / depends on ..." from being mistaken for
        # a dependency of the surrounding menu.
        #
        menu_header_open = False

        for lineno, line in enumerate(lines, 1):
            stripped = line.strip()

            m = IF_RE.match(line)
            if m:
                if_stack.append(m.group(1))
                current = None
                continue

            if ENDIF_RE.match(line):
                if if_stack:
                    if_stack.pop()
                current = None
                continue

            if MENU_RE.match(line):
                menu_stack.append([])
                current = None
                menu_header_open = True
                continue

            if ENDMENU_RE.match(line):
                if menu_stack:
                    menu_stack.pop()

                current = None
                menu_header_open = False
                continue

            #
            # Only dependencies in the menu header itself apply to
            # every entry in that menu.
            #
            m = DEPENDS_RE.match(line)

            if (
                m
                and current is None
                and menu_stack
                and menu_header_open
            ):
                menu_stack[-1].append(m.group(1))
                continue

            #
            # comment/choice/source start independent Kconfig entries.
            # Their own "depends on" expressions must never leak into
            # the surrounding menu.
            #
            if (
                COMMENT_RE.match(line)
                or CHOICE_RE.match(line)
                or ENDCHOICE_RE.match(line)
                or SOURCE_RE.match(line)
            ):
                current = None
                menu_header_open = False
                continue

            m = CONFIG_RE.match(line)
            if m:
                menu_header_open = False
                symbol = m.group(1)

                current = defs.setdefault(
                    symbol,
                    {
                        "prompt": False,
                        "depends": [],
                        "ifs": [],
                        "menu_depends": [],
                        "selects": [],
                        "locations": [],
                    }
                )

                current["ifs"].extend(if_stack)

                for menu_deps in menu_stack:
                    current["menu_depends"].extend(
                        menu_deps
                    )

                current["locations"].append(
                    f"{path}:{lineno}"
                )
                continue

            if current is None:
                continue

            #
            # A new menu/choice/source construct does not terminate
            # a config block, but a new config does. The parser only
            # records properties that match known config attributes.
            #
            if PROMPT_RE.match(line):
                current["prompt"] = True

            m = DEPENDS_RE.match(line)
            if m:
                current["depends"].append(
                    m.group(1)
                )

            m = SELECT_RE.match(line)
            if m:
                target = m.group(1)
                condition = m.group(2)

                current["selects"].append(
                    (target, condition)
                )

                reverse_select.setdefault(
                    target,
                    []
                ).append(
                    (next(
                        (
                            k
                            for k, v in defs.items()
                            if v is current
                        ),
                        None
                    ), condition)
                )

    #
    # Rebuild reverse-select cleanly. The code above keeps parsing simple;
    # doing this second pass guarantees exact source symbols.
    #
    reverse_select = {}

    for source, data in defs.items():
        for target, condition in data["selects"]:
            reverse_select.setdefault(
                target,
                []
            ).append(
                (source, condition)
            )

    return defs, reverse_select


def strip_outer_parens(expr):
    expr = expr.strip()

    while (
        expr.startswith("(")
        and expr.endswith(")")
    ):
        depth = 0
        valid = True

        for i, char in enumerate(expr):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1

                if depth == 0 and i != len(expr) - 1:
                    valid = False
                    break

        if valid:
            expr = expr[1:-1].strip()
        else:
            break

    return expr


def split_top(expr, op):
    parts = []
    depth = 0
    start = 0
    i = 0

    while i < len(expr):
        c = expr[i]

        if c == "(":
            depth += 1
            i += 1
            continue

        if c == ")":
            depth -= 1
            i += 1
            continue

        if (
            depth == 0
            and expr.startswith(op, i)
        ):
            parts.append(
                expr[start:i].strip()
            )
            i += len(op)
            start = i
            continue

        i += 1

    if parts:
        parts.append(
            expr[start:].strip()
        )

    return parts


def symbol_value(symbol, base, requested):
    if symbol in requested:
        return requested[symbol]

    return base.get(symbol, "n")


def atom_satisfied(expr, base, requested):
    expr = strip_outer_parens(expr)

    if expr in ("y", "1"):
        return True

    if expr in ("n", "0"):
        return False

    if expr.startswith("!"):
        return not expression_satisfied(
            expr[1:].strip(),
            base,
            requested
        )

    m = re.match(
        r'^([A-Z][A-Z0-9_]*)\s*=\s*([ymn])$',
        expr
    )

    if m:
        return (
            symbol_value(
                m.group(1),
                base,
                requested
            )
            == m.group(2)
        )

    if re.fullmatch(
        r'[A-Z][A-Z0-9_]*',
        expr
    ):
        return symbol_value(
            expr,
            base,
            requested
        ) in ("y", "m")

    return False


def expression_satisfied(expr, base, requested):
    expr = strip_outer_parens(expr)

    parts = split_top(expr, "||")
    if parts:
        return any(
            expression_satisfied(
                x,
                base,
                requested
            )
            for x in parts
        )

    parts = split_top(expr, "&&")
    if parts:
        return all(
            expression_satisfied(
                x,
                base,
                requested
            )
            for x in parts
        )

    return atom_satisfied(
        expr,
        base,
        requested
    )


def resolve_expression(
    expr,
    base,
    requested,
    unresolved,
    trace,
    parent,
):
    expr = strip_outer_parens(expr)

    if expression_satisfied(
        expr,
        base,
        requested
    ):
        return []

    and_parts = split_top(expr, "&&")

    if and_parts:
        result = []

        for part in and_parts:
            result.extend(
                resolve_expression(
                    part,
                    base,
                    requested,
                    unresolved,
                    trace,
                    parent,
                )
            )

        return result

    or_parts = split_top(expr, "||")

    if or_parts:
        #
        # If one side is already satisfied, no action required.
        #
        for part in or_parts:
            if expression_satisfied(
                part,
                base,
                requested
            ):
                return []

        #
        # Never satisfy a real hardware dependency through COMPILE_TEST.
        #
        real_parts = [
            x for x in or_parts
            if "COMPILE_TEST" not in x
        ]

        if len(real_parts) == 1:
            return resolve_expression(
                real_parts[0],
                base,
                requested,
                unresolved,
                trace,
                parent,
            )

        unresolved.append(
            f"{parent}: ambiguous dependency: {expr}"
        )

        return []

    if expr.startswith("!"):
        #
        # We do not automatically disable symbols.
        #
        unresolved.append(
            f"{parent}: negative dependency not auto-resolved: {expr}"
        )
        return []

    m = re.match(
        r'^([A-Z][A-Z0-9_]*)\s*=\s*y$',
        expr
    )

    if m:
        return [m.group(1)]

    if re.fullmatch(
        r'[A-Z][A-Z0-9_]*',
        expr
    ):
        return [expr]

    unresolved.append(
        f"{parent}: unsupported dependency expression: {expr}"
    )

    return []


def resolve_frontend(symbol, defs, reverse_select):
    data = defs.get(symbol)

    if not data:
        return symbol

    if data["prompt"]:
        return symbol

    candidates = []

    for source, condition in reverse_select.get(
        symbol,
        []
    ):
        if not source:
            continue

        source_data = defs.get(
            source,
            {}
        )

        if source_data.get("prompt"):
            candidates.append(source)

    candidates = sorted(set(candidates))

    if len(candidates) == 1:
        return candidates[0]

    #
    # Generic host-vs-endpoint pattern:
    #
    # FOO internal
    #   selected by FOO_HOST
    #   selected by FOO_EP
    #
    hosts = [
        x for x in candidates
        if x.endswith("_HOST")
    ]

    eps = [
        x for x in candidates
        if x.endswith("_EP")
    ]

    if len(hosts) == 1 and eps:
        return hosts[0]

    return symbol


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve Kconfig dependency closure for a requested fragment"
        )
    )

    parser.add_argument(
        "--kernel",
        required=True
    )

    parser.add_argument(
        "--base-config",
        required=True
    )

    parser.add_argument(
        "--requested",
        required=True
    )

    parser.add_argument(
        "--output",
        required=True
    )

    args = parser.parse_args()

    kernel = Path(args.kernel)
    output = Path(args.output)

    output.mkdir(
        parents=True,
        exist_ok=True
    )

    base = read_config(
        args.base_config
    )

    original = read_config(
        args.requested
    )

    requested = dict(original)

    defs, reverse_select = scan_kconfig(
        kernel
    )

    unresolved = []
    trace = []

    changed = True

    while changed:
        changed = False

        for original_symbol in list(
            sorted(requested)
        ):
            value = requested[
                original_symbol
            ]

            #
            # Both built-in and module requests require their Kconfig
            # dependency closure to be resolved.
            #
            if value not in ("y", "m"):
                continue

            frontend = resolve_frontend(
                original_symbol,
                defs,
                reverse_select
            )

            if frontend != original_symbol:
                trace.append(
                    f"CONFIG_{original_symbol} "
                    f"-> frontend CONFIG_{frontend}"
                )

                del requested[
                    original_symbol
                ]

                if requested.get(
                    frontend
                ) != "y":
                    requested[
                        frontend
                    ] = "y"

                changed = True
                continue

            data = defs.get(
                original_symbol
            )

            if not data:
                unresolved.append(
                    f"CONFIG_{original_symbol}: "
                    "symbol definition not found"
                )
                continue

            expressions = []

            for expr in data["ifs"]:
                expressions.append(
                    ("enclosing-if", expr)
                )

            for expr in data["menu_depends"]:
                expressions.append(
                    ("menu-depends", expr)
                )

            for expr in data["depends"]:
                expressions.append(
                    ("depends", expr)
                )

            for kind, expr in expressions:
                deps = resolve_expression(
                    expr,
                    base,
                    requested,
                    unresolved,
                    trace,
                    f"CONFIG_{original_symbol}",
                )

                for dep in deps:
                    if dep == "COMPILE_TEST":
                        continue

                    dep_value = symbol_value(
                        dep,
                        base,
                        requested
                    )

                    if dep_value == "y":
                        continue

                    if requested.get(
                        dep
                    ) == "y":
                        continue

                    requested[
                        dep
                    ] = "y"

                    trace.append(
                        f"CONFIG_{original_symbol} "
                        f"--{kind} {expr}--> "
                        f"CONFIG_{dep}=y"
                    )

                    changed = True

    #
    # Remove duplicate unresolved messages.
    #
    unresolved = sorted(
        set(unresolved)
    )

    resolved_file = (
        output
        / "resolved-fragment.config"
    )

    resolved_file.write_text(
        "".join(
            f"CONFIG_{symbol}={requested[symbol]}\n"
            for symbol in sorted(requested)
        ),
        encoding="utf-8"
    )

    trace_file = (
        output
        / "dependency-trace.txt"
    )

    trace_file.write_text(
        "\n".join(trace)
        + ("\n" if trace else ""),
        encoding="utf-8"
    )

    unresolved_file = (
        output
        / "unresolved.txt"
    )

    unresolved_file.write_text(
        "\n".join(unresolved)
        + ("\n" if unresolved else ""),
        encoding="utf-8"
    )

    print("Kconfig dependency closure")
    print("--------------------------")
    print(
        f"Original requests: {len(original)}"
    )
    print(
        f"Resolved symbols:  {len(requested)}"
    )
    print(
        f"Added symbols:     "
        f"{len(set(requested) - set(original))}"
    )
    print(
        f"Unresolved:        {len(unresolved)}"
    )
    print()
    print(
        f"Fragment: {resolved_file}"
    )
    print(
        f"Trace:    {trace_file}"
    )
    print(
        f"Pending:  {unresolved_file}"
    )


if __name__ == "__main__":
    main()
