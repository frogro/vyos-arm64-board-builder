#!/usr/bin/env python3
"""Native administrative operations; secrets travel over stdin, never argv/config."""
import argparse
import getpass
import json
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'clients', 'pending', 'pair', 'revoke', 'reset-credentials'])
    parser.add_argument('name')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', args.name):
        parser.error('Invalid container name')
    request = {'action': args.action}
    if args.action != 'status':
        if not sys.stdin.isatty():
            parser.error('This operation requires an interactive terminal')
        if args.action == 'reset-credentials':
            request['username'] = input('New Sunshine Web username: ')
            request['password'] = getpass.getpass('New Web password (at least 12 characters): ')
            if request['password'] != getpass.getpass('Repeat new password: '):
                parser.error('Passwords differ')
        else:
            request['username'] = input('Sunshine Web username: ')
            request['password'] = getpass.getpass('Sunshine Web password: ')
        if args.action == 'pair':
            request['pairing_id'] = input('Pending pairing ID (see pending command): ')
            request['name'] = input('Client name: ')
            request['pin'] = getpass.getpass('Four-digit Moonlight PIN: ')
        if args.action == 'revoke':
            request['uuid'] = input('Client UUID to revoke (see clients command): ')
    result = subprocess.run(['podman', 'exec', '--interactive', '--user', 'kiosk', args.name,
                             'python3', '/usr/local/bin/kiosk-sunshine.py', 'request'],
                            input=json.dumps(request), capture_output=True, text=True, timeout=35)
    if result.stdout:
        try:
            print(json.dumps(json.loads(result.stdout), indent=2, ensure_ascii=True))
        except ValueError:
            print('Unexpected response from kiosk controller', file=sys.stderr)
            return 1
    if result.returncode:
        # Do not echo arbitrary container output; it may contain secrets/control codes.
        print('Operation failed. Check container state and compatible supervisor image.', file=sys.stderr)
    return result.returncode


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.SubprocessError, EOFError, KeyboardInterrupt):
        print('Operation interrupted or container unavailable', file=sys.stderr)
        sys.exit(1)
