#!/usr/bin/env python3

import copy
import importlib
import json
import os
import subprocess
import sys
import tempfile
from ctypes import c_bool, c_char_p, c_void_p, cdll
from pathlib import Path

from vyos.configtree import reference_tree_to_json
from vyos.defaults import reference_tree_cache

NODE_DATA_FIELDS = {
    'node_type',
    'multi',
    'valueless',
    'default_value',
    'owner',
    'priority',
}


def trim_node_data(tree):
    if isinstance(tree, dict):
        for key in list(tree):
            value = tree[key]
            if key == 'node_data' and isinstance(value, dict):
                for field in list(value):
                    if field not in NODE_DATA_FIELDS:
                        del value[field]
            else:
                trim_node_data(value)
    elif isinstance(tree, list):
        for value in tree:
            trim_node_data(value)


def merge_without_override(source, destination, path=()):
    result = copy.deepcopy(destination)

    for key, value in source.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
            continue

        existing = result[key]
        if isinstance(value, dict) and isinstance(existing, dict):
            result[key] = merge_without_override(
                value,
                existing,
                path + (str(key),),
            )
            continue

        if value != existing:
            dotted = '.'.join(path + (str(key),))
            raise RuntimeError(
                f'reference cache collision at {dotted}: '
                f'existing={existing!r} overlay={value!r}'
            )

    return result


def load_lib():
    lib = cdll.LoadLibrary('/usr/lib/libvyosconfig.so.0')

    lib.read_internal_string_reference_tree.argtypes = [c_char_p]
    lib.read_internal_string_reference_tree.restype = c_void_p
    lib.write_internal_reference_tree.argtypes = [c_void_p, c_char_p]
    lib.write_internal_reference_tree.restype = None
    lib.tree_merge.argtypes = [c_bool, c_void_p, c_void_p]
    lib.tree_merge.restype = c_void_p
    lib.destroy.argtypes = [c_void_p]
    lib.destroy.restype = None
    lib.get_error.argtypes = []
    lib.get_error.restype = c_char_p

    return lib


def lib_error(lib):
    raw = lib.get_error()
    return raw.decode(errors='replace') if raw else 'unknown libvyosconfig error'


def merge_binary_reference(existing_cache, overlay_cache, output_cache):
    lib = load_lib()

    existing_ptr = lib.read_internal_string_reference_tree(
        Path(existing_cache).read_bytes()
    )
    if not existing_ptr:
        raise RuntimeError(
            f'unable to read existing reference tree: {lib_error(lib)}'
        )

    overlay_ptr = lib.read_internal_string_reference_tree(
        Path(overlay_cache).read_bytes()
    )
    if not overlay_ptr:
        lib.destroy(existing_ptr)
        raise RuntimeError(
            f'unable to read KVM reference overlay: {lib_error(lib)}'
        )

    merged_ptr = lib.tree_merge(False, existing_ptr, overlay_ptr)
    if not merged_ptr:
        lib.destroy(existing_ptr)
        lib.destroy(overlay_ptr)
        raise RuntimeError(
            f'unable to merge KVM reference overlay: {lib_error(lib)}'
        )

    tmp = Path(str(output_cache) + '.kvm-new')
    try:
        lib.write_internal_reference_tree(
            merged_ptr,
            os.fsencode(tmp),
        )
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise RuntimeError('merged VyOS reftree cache was not written')
        os.replace(tmp, output_cache)
    finally:
        tmp.unlink(missing_ok=True)
        lib.destroy(existing_ptr)
        lib.destroy(overlay_ptr)
        lib.destroy(merged_ptr)


def update_python_reference(overlay_dict):
    cache_module = importlib.import_module('vyos.xml_ref.cache')
    cache_path = Path(cache_module.__file__)
    current = copy.deepcopy(cache_module.reference)

    overlay = copy.deepcopy(overlay_dict)
    trim_node_data(overlay)
    merged = merge_without_override(overlay, current)

    tmp = cache_path.with_name(cache_path.name + '.kvm-new')
    tmp.write_text('reference = ' + repr(merged) + '\n')
    compile(tmp.read_text(), str(cache_path), 'exec')
    os.chmod(tmp, 0o644)
    os.replace(tmp, cache_path)

    pycache = cache_path.parent / '__pycache__'
    if pycache.is_dir():
        for stale in pycache.glob('cache.*.pyc'):
            stale.unlink(missing_ok=True)


def update_configd_include():
    path = Path('/usr/share/vyos/configd-include.json')
    data = json.loads(path.read_text())
    filename = 'service_kvm_over_ip.py'

    if filename not in data:
        data.append(filename)
        data.sort()

    tmp = path.with_name(path.name + '.kvm-new')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def verify_fresh_process():
    code = (
        'from vyos.xml_ref import owner, priority; '
        'p=["service","kvm-over-ip","video","backend"]; '
        'o=owner(p, with_tag=True); '
        'q=priority(p); '
        'print(o); print(q); '
        'assert o == "/usr/libexec/vyos/conf_mode/service_kvm_over_ip.py"; '
        'assert int(q) == 1000'
    )
    subprocess.run(
        [sys.executable, '-c', code],
        check=True,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
    )


def main():
    if len(sys.argv) != 2:
        raise RuntimeError(
            'usage: merge-vyos-reference.py <interface-definition-directory>'
        )

    xml_dir = Path(sys.argv[1]).resolve()
    if not xml_dir.is_dir():
        raise RuntimeError(f'interface-definition directory missing: {xml_dir}')

    existing_binary = Path(reference_tree_cache)
    if not existing_binary.is_file():
        raise RuntimeError(f'VyOS binary reference cache missing: {existing_binary}')

    with tempfile.TemporaryDirectory(prefix='vyos-kvm-ref-') as temp:
        work = Path(temp)
        overlay_json = work / 'overlay.json'
        overlay_binary = work / 'overlay.cache'

        reference_tree_to_json(
            str(xml_dir),
            str(overlay_json),
            internal_cache=str(overlay_binary),
        )

        if not overlay_json.is_file() or not overlay_binary.is_file():
            raise RuntimeError('VyOS reference overlay generation produced no output')

        overlay_dict = json.loads(overlay_json.read_text())

        update_python_reference(overlay_dict)
        merge_binary_reference(
            existing_binary,
            overlay_binary,
            existing_binary,
        )
        update_configd_include()

    verify_fresh_process()
    print('Installed native VyOS KVM-over-IP reference-tree overlay')


if __name__ == '__main__':
    main()
