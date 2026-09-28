#!/usr/bin/env python3
"""Add G to the native container owner, after optional F source preparation."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
HERE = Path(__file__).resolve().parent

def prepare(root):
    root = Path(root)
    owner = root/'src/conf_mode/container.py'
    schema = root/'interface-definitions/container.xml.in'
    helper = root/'python/vyos/receiver.py'
    code, xml = owner.read_text(), schema.read_text()
    if helper.exists() or '<node name="receiver">' in xml:
        raise ValueError('Receiver already installed')
    changes = [
        ('from vyos import ConfigError\n', 'from vyos import ConfigError\nfrom vyos import receiver\nimport subprocess\n'),
        ('    # Add new container\n',
         "    try:\n        interfaces = Config().get_config_dict(['interfaces'], key_mangling=('-', '_')) if any('receiver' in c and 'disable' not in c for c in container.get('name', {}).values()) else {}\n        receiver.verify_all(container, interfaces)\n    except (ValueError, OSError, subprocess.SubprocessError) as error:\n        raise ConfigError(str(error)) from error\n\n    # Add new container\n"),
        ("    if 'health_check' in container_config:\n", "    out.extend(receiver.environment(container_config))\n\n    if 'health_check' in container_config:\n")]
    for old,new in changes:
        if code.count(old) != 1:
            raise ValueError('Native container owner changed: ' + old)
        code = code.replace(old,new)
    anchor = '          <leafNode name="allow-host-pid">'
    if xml.count(anchor) != 1:
        raise ValueError('Native container schema changed')
    fragment = (HERE/'receiver.xml').read_text()
    ET.fromstring(fragment)
    xml = xml.replace(anchor, '\n'.join('          '+s for s in fragment.splitlines())+'\n'+anchor)
    ET.fromstring(re.sub(r'(?m)^\s*#include <[^>]+>\s*$', '', xml))
    compile(code, str(owner), 'exec')
    helper.write_text((HERE/'receiver.py').read_text())
    (root/'op-mode-definitions').mkdir(exist_ok=True)
    (root/'op-mode-definitions/receiver.xml.in').write_text((HERE/'receiver-op.xml').read_text())
    op=root/'src/op_mode/receiver.py'
    op.parent.mkdir(parents=True,exist_ok=True)
    op.write_text((HERE/'receiver-op.py').read_text());op.chmod(0o755)
    schema.write_text(xml); owner.write_text(code)
