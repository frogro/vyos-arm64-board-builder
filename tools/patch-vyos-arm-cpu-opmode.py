#!/usr/bin/env python3
"""Add ARM /proc/cpuinfo fallbacks to the VyOS CPU op-mode renderer."""

from __future__ import annotations

import argparse
import py_compile
from pathlib import Path


OLD_TEMPLATE = """cpu_template = Template(\"\"\"
{% for cpu in cpus %}
{% if 'physical id' in cpu %}CPU socket: {{cpu['physical id']}}{% endif %}
{% if 'vendor_id' in cpu %}CPU Vendor:       {{cpu['vendor_id']}}{% endif %}
{% if 'model name' in cpu %}Model:            {{cpu['model name']}}{% endif %}
{% if 'cpu cores' in cpu %}Cores:            {{cpu['cpu cores']}}{% endif %}
{% if 'cpu MHz' in cpu %}Current MHz:      {{cpu['cpu MHz']}}{% endif %}
{% endfor %}
\"\"\")"""

NEW_TEMPLATE = """cpu_template = Template(\"\"\"
{% for cpu in cpus %}
{% if 'physical id' in cpu %}CPU socket: {{cpu['physical id']}}{% endif %}
{% if 'vendor_id' in cpu %}CPU Vendor:       {{cpu['vendor_id']}}{% elif 'CPU implementer' in cpu %}CPU Implementer:  {{cpu['CPU implementer']}}{% endif %}
{% if 'model name' in cpu %}Model:            {{cpu['model name']}}{% elif 'CPU part' in cpu %}CPU Part:         {{cpu['CPU part']}}{% endif %}
{% if 'cpu cores' in cpu %}Cores:            {{cpu['cpu cores']}}{% endif %}
{% if 'cpu MHz' in cpu %}Current MHz:      {{cpu['cpu MHz']}}{% elif 'BogoMIPS' in cpu %}BogoMIPS:         {{cpu['BogoMIPS']}}{% endif %}
{% if 'CPU architecture' in cpu %}Architecture:     ARMv{{cpu['CPU architecture']}}{% endif %}
{% if 'CPU variant' in cpu %}Variant:          {{cpu['CPU variant']}}{% endif %}
{% if 'CPU revision' in cpu %}Revision:         {{cpu['CPU revision']}}{% endif %}
{% endfor %}
\"\"\")"""

OLD_SUMMARY = "models = [c.get('model name', 'unknown') for c in cpu_data]"
NEW_SUMMARY = (
    "models = [c.get('model name', c.get('CPU part', 'unknown')) "
    "for c in cpu_data]"
)


def patch_cpu_opmode(rootfs: Path) -> bool:
    target = rootfs / "usr/libexec/vyos/op_mode/cpu.py"
    if not target.is_file():
        raise SystemExit(f"VyOS CPU op-mode file is missing: {target}")

    source = target.read_text()
    template_patched = NEW_TEMPLATE in source
    summary_patched = NEW_SUMMARY in source
    if template_patched and summary_patched:
        py_compile.compile(str(target), doraise=True)
        return False
    if template_patched != summary_patched:
        raise SystemExit(f"Refusing partially patched VyOS CPU op-mode file: {target}")
    if source.count(OLD_TEMPLATE) != 1 or source.count(OLD_SUMMARY) != 1:
        raise SystemExit(
            "VyOS CPU op-mode source no longer matches the expected upstream "
            f"implementation: {target}"
        )

    target.write_text(
        source.replace(OLD_TEMPLATE, NEW_TEMPLATE).replace(OLD_SUMMARY, NEW_SUMMARY)
    )
    py_compile.compile(str(target), doraise=True)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rootfs", type=Path)
    args = parser.parse_args()
    changed = patch_cpu_opmode(args.rootfs)
    print("Patched VyOS CPU display for ARM" if changed else "VyOS ARM CPU display already patched")


if __name__ == "__main__":
    main()
