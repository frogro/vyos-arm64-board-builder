#!/usr/bin/env python3
"""Read-only startup media policy report; no browser debugging port is exposed."""
import json
import re
import subprocess
import sys


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', sys.argv[1]):
        raise ValueError('Expected kiosk container name')
    result = subprocess.run(['podman', 'exec', '--user', 'kiosk', sys.argv[1],
                             'python3', '/usr/local/bin/kiosk-media.py', 'status'],
                            capture_output=True, text=True, timeout=5, check=True)
    print(json.dumps(json.loads(result.stdout), indent=2, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError):
        print('Media report unavailable; container must be running a compatible image.', file=sys.stderr)
        sys.exit(1)
