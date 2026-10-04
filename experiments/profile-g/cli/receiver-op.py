#!/usr/bin/env python3
"""Read-only wireless preflight. No AP, interface or driver changes."""
import json
import re
import subprocess
from pathlib import Path
import sys
from vyos.receiver import wifi_report

def main():
    if sys.argv[1:2] == ['media']:
        if len(sys.argv) != 3 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', sys.argv[2]):
            raise SystemExit('Expected receiver container name')
        try:
            result = subprocess.check_output(['podman', 'exec', sys.argv[2], 'python3', '/opt/profile-g/media.py', 'status'], text=True, timeout=15)
            print(json.dumps(json.loads(result), indent=2))
        except (OSError, ValueError, subprocess.SubprocessError):
            raise SystemExit('Media report unavailable; receiver container must be running a compatible image')
        return
    interfaces = sys.argv[1:] or [p.name for p in Path('/sys/class/net').iterdir() if (p/'phy80211').exists()]
    for interface in interfaces:
        try:
            print(json.dumps(wifi_report(interface),indent=2))
        except Exception as error:
            print(json.dumps({'interface':interface,'ready_for_exclusive_miracast':False,'reason':str(error)}))
if __name__=='__main__': main()
