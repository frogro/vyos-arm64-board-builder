#!/usr/bin/env python3
"""Opt-in experiment: extend a clean vyos-1x source before its normal build.

Do not use on installed templates/caches. No normal builder profile enables this.
"""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def parse_template(text):
    # Upstream .xml.in includes are expanded later by transclude-template.
    # Inspect only this file's structure; preserve include lines in its output.
    return ET.fromstring(re.sub(r'(?m)^[ \t]*#include <[^>\n]+>[ \t]*$', '', text))


def prepare(root):
    root = Path(root)
    schema = root / 'interface-definitions/container.xml.in'
    owner = root / 'src/conf_mode/container.py'
    helper = root / 'python/vyos/kiosk.py'
    completion = root / 'src/completion/list-kiosk-outputs.py'
    xml = schema.read_text()
    code = owner.read_text()
    tree = parse_template(xml)
    parent = tree.find("./node[@name='container']/children/tagNode[@name='name']/children")
    if parent is None or parent.find("node[@name='kiosk']") is not None or helper.exists() or completion.exists():
        raise ValueError('Unexpected or already patched source tree')
    anchor = '          <leafNode name="allow-host-pid">'
    checks = [
        ('from vyos import ConfigError\n', 'from vyos import ConfigError\nfrom vyos.kiosk import environment as kiosk_environment\n'),
        ('        for name, container_config in container[\'name\'].items():\n            # Container image',
         '        for name, container_config in container[\'name\'].items():\n'
         '            try:\n                kiosk_environment(container_config)\n'
         '            except ValueError as error:\n                raise ConfigError(f\'Kiosk "{name}": {error}\') from error\n'
         '            # Container image'),
        ("    if 'health_check' in container_config:\n", "    out.extend(kiosk_environment(container_config))\n\n    if 'health_check' in container_config:\n"),
    ]
    if xml.count(anchor) != 1:
        raise ValueError('Container schema changed; review required')
    for old, new in checks:
        if code.count(old) != 1:
            raise ValueError('Container owner changed; review required: ' + old[:65])
        code = code.replace(old, new)
    fragment = (HERE / 'kiosk.xml').read_text()
    ET.fromstring(fragment)
    xml = xml.replace(anchor, '\n'.join('          ' + line for line in fragment.splitlines()) + '\n' + anchor)
    compile(code, str(owner), 'exec')
    parse_template(xml)
    helper.write_text((HERE / 'kiosk.py').read_text())
    completion.parent.mkdir(parents=True, exist_ok=True)
    completion.write_text((HERE / 'list-kiosk-outputs.py').read_text())
    completion.chmod(0o755)
    schema.write_text(xml)
    owner.write_text(code)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    prepare(parser.parse_args().source)
