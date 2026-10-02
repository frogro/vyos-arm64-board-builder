#!/usr/bin/env python3
"""Download the exact signed-repository ARM64 kernel, or request a source build.

Network/signature failures are errors, never evidence that a package is missing.
No packages are installed on the runner. Built packages are validated separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def expected(source):
    defaults = tomllib.loads((source/'data/defaults.toml').read_text())
    version, flavor = defaults['kernel_version'], defaults['kernel_flavor']
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) or not re.fullmatch(r'[a-z0-9-]+', flavor):
        raise ValueError('Unsupported kernel identity; review upstream defaults')
    return defaults, f'{version}-{flavor}'


def candidate(text):
    match = re.search(r'^\s*Candidate:\s*(\S+)', text, re.M)
    if not match or match[1] == '(none)':
        return None
    return match[1]


def validate(deb, release):
    fields = subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Package', 'Architecture', 'Version'], text=True)
    data = dict(line.split(': ', 1) for line in fields.splitlines())
    if data.get('Package') != 'linux-image-'+release or data.get('Architecture') != 'arm64':
        raise ValueError('Kernel package identity/architecture mismatch: '+str(data))
    listing = subprocess.check_output(['dpkg-deb', '-c', str(deb)], text=True)
    if not any(line.split()[-1] == './boot/vmlinuz-'+release for line in listing.splitlines()):
        raise ValueError('Kernel payload lacks the expected vmlinuz')
    return data


def record(deb, release, mode, source, output):
    info = validate(deb, release)
    with deb.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    output.write_text(json.dumps(dict(schema=1, mode=mode, kernel_release=release,
        source_commit=subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(),
        package=deb.name, sha256=digest, **info), indent=2)+'\n')


def probe(source, packages, metadata):
    defaults, release = expected(source)
    package = 'linux-image-'+release
    mirror, branch = defaults['vyos_mirror'], defaults['vyos_branch']
    if not mirror.startswith('https://') or any(c.isspace() for c in mirror) or not re.fullmatch(r'[a-zA-Z0-9._-]+', branch):
        raise ValueError('Invalid signed repository configuration')
    packages.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vyarm-kernel-apt-') as tmp:
        root = Path(tmp)
        (root/'lists/partial').mkdir(parents=True)
        (root/'archives/partial').mkdir(parents=True)
        (root/'status').touch()
        key = root/'vyos.asc'
        shutil.copyfile(source/'data/live-build-config/archives/vyos-dev.key.chroot', key)
        (root/'sources.list').write_text(f'deb [arch=arm64 signed-by={key}] {mirror} {branch} main\n')
        options = ['-o', 'APT::Architecture=arm64', '-o', 'APT::Sandbox::User=root',
                   '-o', 'APT::Update::Error-Mode=any', '-o', 'Acquire::Retries=3',
                   '-o', f'Dir::Etc::sourcelist={root}/sources.list', '-o', 'Dir::Etc::sourceparts=-',
                   '-o', f'Dir::State::lists={root}/lists', '-o', f'Dir::State::status={root}/status',
                   '-o', f'Dir::Cache::archives={root}/archives',
                   '-o', f'Dir::Cache::pkgcache={root}/pkgcache.bin', '-o', f'Dir::Cache::srcpkgcache={root}/srcpkgcache.bin']
        run('apt-get', *options, 'update')
        policy = subprocess.check_output(['apt-cache', *options, 'policy', package+':arm64'], text=True)
        version = candidate(policy)
        if version is None:
            print(f'{package}: absent from successfully verified index; exact-source build required')
            metadata.write_text(json.dumps(dict(schema=1, mode='source-required', kernel_release=release))+'\n')
            return True
        run('apt-get', *options, 'download', package+':arm64='+version, cwd=root)
        files = list(root.glob('*.deb'))
        if len(files) != 1:
            raise ValueError('Expected exactly one downloaded kernel package')
        validate(files[0], release)
        target = packages/files[0].name
        shutil.copyfile(files[0], target)
        record(target, release, 'signed-repository', source, metadata)
        return False


def import_built(source, packages, metadata):
    _, release = expected(source)
    files = list((source/'scripts/package-build/linux-kernel').glob('linux-image-'+release+'_*.deb'))
    if len(files) != 1:
        raise ValueError('Expected exactly one locally built matching kernel image package')
    validate(files[0], release)
    packages.mkdir(parents=True, exist_ok=True)
    target = packages/files[0].name
    shutil.copyfile(files[0], target)
    record(target, release, 'exact-source-build', source, metadata)


def verify_artifact(source, packages, metadata):
    _, release = expected(source)
    data = json.loads(metadata.read_text())
    filename = data['package']
    if Path(filename).name != filename or not filename.endswith('.deb'):
        raise ValueError('Invalid artifact filename')
    if data['kernel_release'] != release or data['source_commit'] != subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip():
        raise ValueError('Kernel provenance mismatch')
    deb = packages/filename
    with deb.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != data['sha256']:
            raise ValueError('Kernel artifact checksum mismatch')
    if sorted(p.name for p in packages.glob('*.deb')) != [filename]:
        raise ValueError('Unexpected additional local packages')
    validate(deb, release)
    print('Verified exact kernel artifact:', filename)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--packages', type=Path, required=True)
    p.add_argument('--metadata', type=Path, required=True)
    modes = p.add_mutually_exclusive_group()
    modes.add_argument('--import-built', action='store_true')
    modes.add_argument('--verify-artifact', action='store_true')
    a = p.parse_args()
    a.metadata.parent.mkdir(parents=True, exist_ok=True)
    if a.verify_artifact:
        verify_artifact(a.source, a.packages, a.metadata)
    elif a.import_built:
        import_built(a.source, a.packages, a.metadata)
    else:
        build = probe(a.source, a.packages, a.metadata)
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write(f'build_required={str(build).lower()}\n')
