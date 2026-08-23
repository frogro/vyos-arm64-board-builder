#!/usr/bin/env python3
"""Teach VyOS add system image to install board-specific DTBs."""

from __future__ import annotations

import argparse
import py_compile
from pathlib import Path


TARGET_REL = Path(
    "usr/libexec/vyos/op_mode/image_installer.py"
)

ADD_IMAGE_ANCHOR = """\
@compat.grub_cfg_update
def add_image("""

ROOT_DIR_ANCHOR = """\
        root_dir: str = disk.find_persistence()"""

HELPER_BLOCK = r'''def _load_board_update_json(path: Path, description: str) -> dict:
    try:
        data = loads(path.read_text())
    except (OSError, ValueError) as err:
        raise RuntimeError(
            f'Unable to read {description}: {path}: {err}'
        ) from err

    if not isinstance(data, dict):
        raise RuntimeError(
            f'Invalid {description}: expected JSON object: {path}'
        )

    return data


def _validate_board_update_dtb_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError(
            'Invalid board update manifest: device_tree is missing'
        )

    if value != value.strip():
        raise RuntimeError(
            'Invalid board update manifest: device_tree has outer whitespace'
        )

    if (
        value.startswith('/')
        or '\\' in value
        or '"' in value
        or any(ord(ch) < 32 for ch in value)
    ):
        raise RuntimeError(
            f'Invalid board update device_tree path: {value!r}'
        )

    parts = value.split('/')

    if (
        any(part in ('', '.', '..') for part in parts)
        or '/'.join(parts) != value
        or not value.endswith('.dtb')
    ):
        raise RuntimeError(
            f'Invalid board update device_tree path: {value!r}'
        )

    return value


def _copy_board_dtb_from_update_iso(
    iso_root: Path,
    root_dir: Path,
    image_name: str,
    profile_path: Path = Path(
        '/usr/share/vyos-arm64-board-builder/profile.json'
    ),
) -> bool:
    # Non-builder VyOS installations keep the normal upstream behaviour.
    if not profile_path.is_file():
        return False

    profile = _load_board_update_json(
        profile_path,
        'installed board profile',
    )

    manifest_path = iso_root / 'board-manifest.json'

    if not manifest_path.is_file():
        raise RuntimeError(
            'This board-aware VyOS installation requires an update ISO '
            'containing board-manifest.json'
        )

    manifest = _load_board_update_json(
        manifest_path,
        'board update manifest',
    )

    if manifest.get('schema') != 3:
        raise RuntimeError(
            'Unsupported board update manifest schema: '
            f'{manifest.get("schema")!r}'
        )

    for field in ('architecture', 'board'):
        current_value = profile.get(field)
        update_value = manifest.get(field)

        if (
            not isinstance(current_value, str)
            or not current_value
            or not isinstance(update_value, str)
            or not update_value
        ):
            raise RuntimeError(
                f'Board update metadata is missing required field: {field}'
            )

        if current_value != update_value:
            raise RuntimeError(
                f'Board update {field} mismatch: '
                f'installed={current_value!r}, update={update_value!r}'
            )

    dtb = _validate_board_update_dtb_path(
        manifest.get('device_tree')
    )

    source = iso_root / 'live' / 'dtb' / dtb

    if not source.is_file():
        raise RuntimeError(
            f'Board DTB is missing from update ISO: {source}'
        )

    destination = (
        root_dir
        / 'boot'
        / image_name
        / 'dtb'
        / dtb
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    copy(source, destination)

    print(
        'Installed board DTB: '
        f'/boot/{image_name}/dtb/{dtb}'
    )

    return True
'''

NEW_ROOT_DIR_BLOCK = ROOT_DIR_ANCHOR + r'''

        _copy_board_dtb_from_update_iso(
            Path(DIR_ISO_MOUNT),
            Path(root_dir),
            image_name,
        )'''


def patch_image_installer(rootfs: Path) -> bool:
    target = rootfs / TARGET_REL

    if not target.is_file():
        raise SystemExit(
            f"VyOS image installer is missing: {target}"
        )

    source = target.read_text()

    helper_present = (
        "def _copy_board_dtb_from_update_iso(" in source
    )
    call_present = (
        "_copy_board_dtb_from_update_iso(\n"
        "            Path(DIR_ISO_MOUNT)," in source
    )

    if helper_present and call_present:
        py_compile.compile(
            str(target),
            doraise=True,
        )
        return False

    if helper_present != call_present:
        raise SystemExit(
            "Refusing partially patched VyOS image installer: "
            f"{target}"
        )

    if source.count(ADD_IMAGE_ANCHOR) != 1:
        raise SystemExit(
            "VyOS image installer no longer matches the expected "
            f"add_image implementation: {target}"
        )

    if source.count(ROOT_DIR_ANCHOR) != 1:
        raise SystemExit(
            "VyOS image installer no longer matches the expected "
            f"persistence-directory implementation: {target}"
        )

    source = source.replace(
        ADD_IMAGE_ANCHOR,
        HELPER_BLOCK
        + "\n\n"
        + ADD_IMAGE_ANCHOR,
        1,
    )

    source = source.replace(
        ROOT_DIR_ANCHOR,
        NEW_ROOT_DIR_BLOCK,
        1,
    )

    target.write_text(source)

    py_compile.compile(
        str(target),
        doraise=True,
    )

    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "rootfs",
        type=Path,
    )
    args = parser.parse_args()

    changed = patch_image_installer(
        args.rootfs,
    )

    if changed:
        print(
            "Patched VyOS add system image for board DTB updates"
        )
    else:
        print(
            "VyOS add system image already supports board DTB updates"
        )


if __name__ == "__main__":
    main()
