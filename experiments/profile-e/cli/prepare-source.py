#!/usr/bin/env python3
"""Stage native E/shared USB sources for upstream VyOS generation.

Call once with the combined E/G selection
so there is exactly one USB owner/service. Never modify generated CLI caches.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent


def prepare(root, print_server=False, receiver=False):
    root = Path(root)
    if not print_server and not receiver:
        return []
    files = {}
    roles = ['usb-server'] + (['print-server'] if print_server else [])
    for role in roles:
        xml = (HERE/('service_'+role+'.xml')).read_text()
        ET.fromstring(xml)
        files['interface-definitions/service_'+role+'.xml.in'] = xml
        owner = (HERE/'service.py').read_text().replace(
            '/usr/local/libexec/vyarm-print-supervisor.py', '/usr/libexec/vyos/vyarm-print-supervisor.py')
        compile(owner, role, 'exec')
        files['src/conf_mode/service_'+role.replace('-','_')+'.py'] = owner
        unit = 'vyarm-print' if role=='print-server' else 'vyarm-usb'
        # The native owner replaces this inactive template with the selected
        # configuration under /run. Nothing is enabled before a VyOS commit.
        files['src/systemd/'+unit+'.service'] = '[Unit]\nDescription=VyARM '+role+' (not configured)\n[Service]\nType=oneshot\nExecStart=/bin/true\n'
    files['op-mode-definitions/request_usb-server.xml.in'] = (HERE/'request_usb-server.xml').read_text()
    files['src/helpers/vyarm-install-virtualhere.py'] = (HERE/'install-virtualhere.py').read_text()
    if print_server:
        files['op-mode-definitions/request_print-server.xml.in'] = (HERE/'request_print-server.xml').read_text()
        files['src/helpers/vyarm-print-password.py'] = (HERE/'print-password.py').read_text()
        files['src/helpers/vyarm-print-supervisor.py'] = (HERE/'cups-supervisor.py').read_text()
    for name in files:
        if (root/name).exists():
            raise ValueError('Refusing to overwrite existing profile source: '+name)
    for name, text in files.items():
        path = root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text)
        path.chmod(0o755 if name.endswith('.py') else 0o644)
    return sorted(files)
