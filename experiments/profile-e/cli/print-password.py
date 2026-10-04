#!/usr/bin/python3
"""Change only the CUPS account, retaining the secret across image updates."""
import getpass
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo')
    password = getpass.getpass('New CUPS password for vyos: ')
    if not password or any(c in password for c in '\n\r\0'):
        raise SystemExit('Password must be nonempty and contain no line breaks or NUL')
    if password != getpass.getpass('Repeat password: '):
        raise SystemExit('Passwords do not match; unchanged')
    root = Path('/config/profile-e')
    root.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.password-', dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(password + '\n')
        os.replace(name, root / 'admin-password')
    finally:
        Path(name).unlink(missing_ok=True)
    # Recreate the secret bind mount and apply the password at container start.
    subprocess.run(['systemctl', 'try-restart', 'vyarm-print.service'], check=True)
    print('CUPS password saved. The VyOS login password is unchanged.')


if __name__ == '__main__':
    main()
