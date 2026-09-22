#!/usr/bin/env python3
"""Resolve one immutable VyOS source and an attested reusable raw artifact."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
RECIPE_FILES = ('.github/workflows/test-vyos-arm64-raw.yml',
                'sources/vyos.sh', 'tools/patch-vyos-arm64-raw.py',
                'profiles/vyos-flavors/arm64-raw.toml')


def recipe_hash():
    digest = hashlib.sha256()
    for name in RECIPE_FILES:
        digest.update(name.encode() + b'\0' + (ROOT / name).read_bytes() + b'\0')
    return digest.hexdigest()


def gh(*args):
    return subprocess.check_output(['gh', *args], text=True)


def reusable(repo, run, commit, recipe, explicit=False):
    if run['conclusion'] != 'success':
        return False
    # Only workflows which produce the supported base format are accepted.
    if run.get('path', '').split('@')[0] not in (
        '.github/workflows/test-vyos-arm64-raw.yml',
        '.github/workflows/build-board-candidate.yml',
    ):
        return False
    names = set(gh('api', '--paginate',
                   f'repos/{repo}/actions/runs/{run["id"]}/artifacts',
                   '--jq', '.artifacts[] | select(.expired == false) | .name').splitlines())
    if not {'vyos-arm64-raw', 'vyos-arm64-raw-provenance'} <= names:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        gh('run', 'download', str(run['id']), '--repo', repo,
           '--name', 'vyos-arm64-raw-provenance', '--dir', tmp)
        source = Path(tmp, 'vyos-source-commit.txt')
        recipe_file = Path(tmp, 'raw-recipe-sha256.txt')
        return (source.is_file() and source.read_text().strip() == commit
                and (explicit or (recipe_file.is_file()
                     and recipe_file.read_text().strip() == recipe)))


def resolve(repo, ref, requested=''):
    if not ref or ref.startswith('-') or any(c.isspace() for c in ref):
        raise ValueError('Invalid VyOS ref')
    commit = json.loads(gh('api', f'repos/vyos/vyos-build/commits/{quote(ref, safe="")}'))['sha']
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Invalid resolved source commit')
    recipe = recipe_hash()
    if os.environ.get('FORCE_FRESH_BASE', '').lower() == 'true':
        if requested and requested != 'auto':
            raise ValueError('Fresh base and explicit raw run cannot be combined')
        return commit, '', recipe
    if requested and requested != 'auto':
        if not requested.isdigit():
            raise ValueError('Invalid raw run ID')
        runs = [json.loads(gh('api', f'repos/{repo}/actions/runs/{requested}'))]
    else:
        # A bounded cache search: a miss safely builds a new base.
        runs = json.loads(gh('api', f'repos/{repo}/actions/runs?status=success&per_page=100'))['workflow_runs']
    for run in runs:
        if reusable(repo, run, commit, recipe, explicit=bool(requested and requested != 'auto')):
            return commit, str(run['id']), recipe
    if requested and requested != 'auto':
        raise ValueError('Requested raw run is unavailable or lacks matching VyOS source provenance; refusing an incompatible base')
    return commit, '', recipe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY'))
    parser.add_argument('--ref', default=os.environ.get('VYOS_REF', 'rolling'))
    parser.add_argument('--run-id', default=os.environ.get('RAW_RUN_ID_REQUESTED', ''))
    parser.add_argument('--recipe-only', action='store_true')
    args = parser.parse_args()
    if args.recipe_only:
        print(recipe_hash())
        return
    commit, run, recipe = resolve(args.repo, args.ref, args.run_id)
    output = f'vyos_commit={commit}\nraw_run_id={run}\nrecipe_sha256={recipe}\n'
    print(output, end='')
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write(output)


if __name__ == '__main__':
    main()
