#!/usr/bin/env python3
"""Keep numeric-looking image names/version strings intact in VyOS tables."""
import argparse
import ast
from pathlib import Path


FUNCTIONS = ('_format_show_images_summary', '_format_show_images_details')


def patch(rootfs: Path) -> bool:
    target = rootfs / 'usr/libexec/vyos/op_mode/image_info.py'
    source = target.read_bytes()
    tree = ast.parse(source, filename=str(target))
    lines = source.splitlines(keepends=True)
    edits = []
    for name in FUNCTIONS:
        functions = [node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(functions) != 1:
            raise ValueError(f'Unexpected image_info implementation: {name}')
        calls = [node for node in ast.walk(functions[0])
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                 and node.func.id == 'tabulate']
        if len(calls) != 1:
            raise ValueError(f'Expected one tabulate call in {name}')
        call = calls[0]
        if ([arg.id if isinstance(arg, ast.Name) else None for arg in call.args]
                != ['table_data', 'headers']
                or any(kw.arg not in ('colalign', 'disable_numparse') for kw in call.keywords)):
            raise ValueError(f'Unexpected tabulate arguments in {name}; review upstream')
        existing = [kw.value for kw in call.keywords if kw.arg == 'disable_numparse']
        if existing:
            if len(existing) == 1 and isinstance(existing[0], ast.Constant) and existing[0].value is True:
                continue  # Also accept an equivalent fix already supplied upstream.
            raise ValueError(f'Unexpected disable_numparse policy in {name}')
        # AST columns are byte offsets. Preserve upstream formatting and all other code.
        end = sum(map(len, lines[:call.end_lineno - 1])) + call.end_col_offset
        if source[end - 1:end] != b')':
            raise ValueError(f'Unexpected tabulate call ending in {name}')
        before = source[:end - 1].rstrip()
        addition = b' disable_numparse=True' if before.endswith(b',') else b', disable_numparse=True'
        edits.append((end - 1, addition))
    for offset, addition in sorted(edits, reverse=True):
        source = source[:offset] + addition + source[offset:]
    compile(source, str(target), 'exec')
    if edits:
        target.write_bytes(source)
    return bool(edits)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rootfs', type=Path)
    changed = patch(parser.parse_args().rootfs)
    print('Fixed image-name table formatting' if changed else 'Image-name formatting already fixed')
