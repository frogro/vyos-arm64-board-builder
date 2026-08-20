#!/usr/bin/env python3

import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "set-grub-console-default.py"


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        grub = Path(temporary) / "boot" / "grub"
        cfg_dir = grub / "grub.cfg.d"
        cfg_dir.mkdir(parents=True)
        defaults = cfg_dir / "20-vyos-defaults-autoload.cfg"
        defaults.write_text(
            'set bootmode="normal"\n'
            'set console_type="ttyAMA"\n'
            'set console_num="0"\n'
            'set console_speed="115200"\n',
            encoding="utf-8",
        )

        subprocess.run(
            ["python3", str(TOOL), str(grub)],
            check=True,
        )

        result = defaults.read_text(encoding="utf-8")
        assert 'set console_type="tty"\n' in result
        assert 'set console_type="ttyAMA"' not in result
        assert 'set console_num="0"\n' in result
        assert 'set bootmode="normal"\n' in result
        assert 'set console_speed="115200"\n' in result

    print("PASS: graphical GRUB console default")


if __name__ == "__main__":
    main()
