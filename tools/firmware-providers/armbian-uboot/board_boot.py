"""Native U-Boot lifecycle adapter. Installed only in extlinux board images."""
from contextlib import contextmanager
from functools import wraps
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid5, NAMESPACE_URL

PROFILE = Path('/usr/share/vyos-arm64-board-builder/boot-provider.json')
CFG = Path('boot/grub/grub.cfg.d')
VERSIONS = CFG / 'vyos-versions'
DEFAULTS = CFG / '20-vyos-defaults-autoload.cfg'
METHOD = 'uboot-extlinux'


def read_json(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise RuntimeError(f'Invalid boot metadata: {path}')
    return value


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}', value):
        raise RuntimeError(f'Invalid image name: {value!r}')
    return value


def dtb_path(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_./+-]+\.dtb', value):
        raise RuntimeError('Invalid DTB path')
    if value.startswith('/') or any(p in ('', '.', '..') for p in value.split('/')):
        raise RuntimeError('DTB path must be relative and normalized')
    return value


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.vyos-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def grub_vars(root):
    result = {}
    for line in (Path(root) / DEFAULTS).read_text().splitlines():
        match = re.fullmatch(r'''set (\w+)=["']?([^"'\n]*)["']?''', line)
        if match:
            result[match[1]] = match[2]
    return result


def boot_options(cfg, version, metadata, variables):
    matches = re.findall(r'^\s*set boot_opts="([^"$\n]+)"\s*$', cfg.read_text(), re.M)
    if len(matches) != 1:
        raise RuntimeError(f'Cannot derive unambiguous boot options: {cfg}')
    tokens = matches[0].split()
    if f'vyos-union=/boot/{version}' not in tokens:
        raise RuntimeError('Boot options do not match the installed image')
    tokens = [t for t in tokens if not t.startswith(('BOOT_IMAGE=', 'console='))]
    # VyOS uses BOOT_IMAGE to distinguish installed and live systems and to
    # identify renamed/custom-named images. Native U-Boot does not add it.
    tokens.insert(0, f'BOOT_IMAGE=/boot/{version}/vmlinuz')
    console = metadata['console']
    baud = str(metadata['baud'])
    kind = variables.get('console_type')
    number = variables.get('console_num', '')
    if kind in ('ttyS', 'ttyAMA') and number.isdigit():
        console = kind + number
        baud = variables.get('console_speed', baud)
    if not re.fullmatch(r'tty(?:S|AMA)\d+', console) or not baud.isdigit():
        raise RuntimeError('Invalid serial console metadata')
    tokens.append(f'console={console},{baud}n8')
    if metadata.get('display_console'):
        tokens.append('console=tty1')
    if variables.get('boot_toram') == 'yes':
        tokens.append('toram')
    mode = variables.get('bootmode', 'normal')
    if mode == 'recovery':
        tokens.append('init=/usr/bin/busybox')
        tokens.append('init')
    elif mode == 'pw_reset':
        tokens.append('init=/usr/libexec/vyos/system/standalone_root_pw_reset')
    elif mode != 'normal':
        raise RuntimeError(f'Unsupported native boot mode: {mode}')
    return ' '.join(tokens)


def sync(root, firmware, metadata):
    """Publish immutable version payloads before replacing either boot menu.

    No kernel of an existing entry is overwritten. Both menu copies always
    refer to complete payloads. Unreferenced payloads are retained for recovery;
    prune() runs only after both menus have been durably replaced.
    """
    root, firmware = Path(root), Path(firmware)
    variables = grub_vars(root)
    configs = sorted((root / VERSIONS).glob('*.cfg'))
    if not configs:
        raise RuntimeError('Refusing an empty native boot menu')
    default_uuid = variables.get('default', '')
    entries, needed = [], set()
    default_label = None
    for cfg in configs:
        version = name(cfg.stem)
        directory = root / 'boot' / version
        info = read_json(directory / 'board-boot.json')
        for key in ('board', 'architecture', 'firmware_provider', 'update_provider', 'profile'):
            if info.get(key) != metadata.get(key):
                raise RuntimeError(f'Incompatible {key} in image {version}')
        dtb = dtb_path(info.get('device_tree'))
        sources = [directory / 'vmlinuz', directory / 'initrd.img', directory / 'dtb' / dtb]
        digest = hashlib.sha256()
        for source in sources:
            if not source.is_file() or source.stat().st_size == 0:
                raise RuntimeError(f'Boot payload missing: {source}')
            digest.update(source.name.encode())
            with source.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
        token = digest.hexdigest()
        destination = firmware / 'vyos-boot' / 'payloads' / token
        needed.add(token)
        if not destination.is_dir():
            size = sum(source.stat().st_size for source in sources)
            if shutil.disk_usage(firmware).free < size + 1024 * 1024:
                raise RuntimeError('Boot partition full: delete an unused VyOS image before adding another')
            destination.parent.mkdir(parents=True, exist_ok=True)
            stage = Path(tempfile.mkdtemp(prefix='.stage-', dir=destination.parent))
            try:
                for source, target in zip(sources, ('Image', 'initrd.img', 'board.dtb')):
                    shutil.copyfile(source, stage / target)
                    with (stage / target).open('rb') as stream:
                        os.fsync(stream.fileno())
                os.replace(stage, destination)
            finally:
                if stage.exists():
                    shutil.rmtree(stage)
        if not all((destination / p).is_file() for p in ('Image', 'initrd.img', 'board.dtb')):
            raise RuntimeError(f'Incomplete cached boot payload: {destination}')
        label = 'vyos-' + uuid5(NAMESPACE_URL, version).hex
        if str(uuid5(NAMESPACE_URL, version)) == default_uuid:
            default_label = label
        prefix = '/vyos-boot/payloads/' + token
        entries.append(f'LABEL {label}\n    MENU LABEL VyOS {version}\n'
                       f'    LINUX {prefix}/Image\n    INITRD {prefix}/initrd.img\n'
                       f'    FDT {prefix}/board.dtb\n'
                       f'    APPEND {boot_options(cfg, version, info, variables)}\n')
    if default_label is None:
        raise RuntimeError('VyOS default image is not available to native U-Boot')
    menu = (f'DEFAULT {default_label}\nTIMEOUT 50\nMENU TITLE VyOS ARM64\n\n' + '\n'.join(entries)).encode()
    # Flush payload directory entries before pointing the firmware to them.
    os.sync()
    paths = [firmware / 'boot/extlinux/extlinux.conf', firmware / 'extlinux/extlinux.conf']
    previous = [(p, p.read_bytes() if p.exists() else None) for p in paths]
    try:
        for p in paths:
            atomic_write(p, menu)
    except Exception:
        for p, data in previous:
            if data is not None:
                atomic_write(p, data)
            else:
                p.unlink(missing_ok=True)
        raise
    for directory in (firmware / 'vyos-boot/payloads').iterdir():
        if re.fullmatch(r'[0-9a-f]{64}', directory.name) and directory.name not in needed:
            try:
                shutil.rmtree(directory)
            except OSError as error:
                print(f'Unused boot payload retained: {error}')
    os.sync()


@contextmanager
def mounted_firmware(root, metadata):
    """Resolve the provider partition on the persistence disk, never by label."""
    source = subprocess.check_output(['findmnt', '-nro', 'SOURCE', '--target', str(root)], text=True).strip().split('[')[0]
    device = Path(source).resolve()
    sysnode = Path('/sys/class/block') / device.name
    if not (sysnode / 'partition').is_file():
        raise RuntimeError('Native boot requires partition-backed persistence')
    parent = sysnode.resolve().parent
    number = str(metadata['firmware_partition'])
    candidates = [p for p in parent.iterdir() if (p / 'partition').is_file() and (p / 'partition').read_text().strip() == number]
    if len(candidates) != 1:
        raise RuntimeError('Cannot resolve firmware partition on the persistence disk')
    part = Path('/dev') / candidates[0].name
    if subprocess.check_output(['blkid', '-s', 'TYPE', '-o', 'value', str(part)], text=True).strip() != 'vfat':
        raise RuntimeError('Native firmware partition is not FAT')
    with tempfile.TemporaryDirectory(prefix='vyos-boot-', dir='/run') as mount:
        subprocess.run(['mount', '-o', 'rw', str(part), mount], check=True)
        try:
            marker = read_json(Path(mount) / 'vyos-boot/provider.json')
            for key in ('board', 'update_provider'):
                if marker.get(key) != metadata.get(key):
                    raise RuntimeError('Firmware partition does not belong to this board provider')
            yield Path(mount)
        finally:
            subprocess.run(['umount', mount], check=True)


def decorate(function):
    """Keep GRUB's authoritative image state and native menus consistent."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        if not PROFILE.is_file():
            return function(*args, **kwargs)
        from vyos.system import disk
        bound = inspect.signature(function).bind(*args, **kwargs)
        bound.apply_defaults()
        root = Path(bound.arguments.get('root_dir') or disk.find_persistence())
        metadata = read_json(PROFILE)
        with open('/run/lock/vyos-native-boot.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            with mounted_firmware(root, metadata) as firmware:
                # Snapshot only the small GRUB metadata files, not image payloads.
                before = {p: p.read_bytes() for p in (root / CFG).rglob('*.cfg')}
                try:
                    result = function(*args, **kwargs)
                    sync(root, firmware, metadata)
                    return result
                except Exception:
                    for p in (root / CFG).rglob('*.cfg'):
                        if p not in before:
                            p.unlink()
                    for p, data in before.items():
                        atomic_write(p, data)
                    raise
    return wrapped
