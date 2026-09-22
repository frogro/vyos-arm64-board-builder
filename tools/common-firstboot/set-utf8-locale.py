#!/usr/bin/env python3
"""Apply image-default UTF-8 locale without removing unrelated environment entries."""
import pathlib
import re
import sys

root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/")
for relative in ("etc/default/locale", "etc/environment"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text() if path.exists() else ""
    lines = [line for line in old.splitlines()
             if not re.match(r"^\s*(?:export\s+)?(?:LANG|LC_ALL)\s*=", line)]
    path.write_text("\n".join(lines + ["LANG=C.UTF-8", "LC_ALL=C.UTF-8"]) + "\n")
path = root / "etc/systemd/system.conf.d/10-vyos-arm64-locale.conf"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("[Manager]\nDefaultEnvironment=LANG=C.UTF-8 LC_ALL=C.UTF-8\n")
