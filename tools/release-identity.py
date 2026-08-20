#!/usr/bin/env python3
"""Derive deterministic VyOS-style release names for one ARM64 board."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import re
import shlex


VERSION_RE = re.compile(
    r"^(?P<series>[0-9]+\.[0-9]+)-"
    r"(?P<train>[a-z0-9][a-z0-9.-]*)-"
    r"(?P<stamp>[0-9]{12})$"
)
BOARD_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def derive(version: str, board: str, profile: str = "base") -> dict[str, str]:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(
            "version must look like 1.5-rolling-YYYYMMDDHHMM: " + version
        )
    if BOARD_RE.fullmatch(board) is None:
        raise ValueError("invalid board slug: " + board)
    if BOARD_RE.fullmatch(profile) is None:
        raise ValueError("invalid profile slug: " + profile)

    stamp = match.group("stamp")
    parsed = datetime.strptime(stamp, "%Y%m%d%H%M")
    train = match.group("train")

    return {
        "VYOS_VERSION": version,
        "BUILD_PROFILE": profile,
        "RELEASE_BASENAME": f"vyos-{version}-{board}-{profile}",
        "RELEASE_TAG": f"{parsed:%Y.%m.%d-%H%M}-{train}-{board}-{profile}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--board", required=True)
    parser.add_argument("--profile", default="base")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    values = derive(args.version, args.board, args.profile)
    text = "".join(
        f"{name}={shlex.quote(value)}\n" for name, value in values.items()
    )

    if args.output is None:
        print(text, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)


if __name__ == "__main__":
    main()
