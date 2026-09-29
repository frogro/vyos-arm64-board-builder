#!/usr/bin/env python3
"""Compare loaded OCI layers/config, accepting Docker's inert empty defaults."""
import json
import re
import subprocess
from pathlib import Path

proof = {}
empty_defaults = {'Hostname', 'Domainname', 'User', 'AttachStdin', 'AttachStdout',
                  'AttachStderr', 'Tty', 'OpenStdin', 'StdinOnce', 'Cmd', 'Image',
                  'Volumes', 'WorkingDir', 'ArgsEscaped', 'StopSignal', 'OnBuild',
                  'Shell', 'Healthcheck', 'ExposedPorts', 'NetworkDisabled',
                  'Labels', 'Entrypoint', 'Env'}
for label, image in [('cli', 'vyos-profile-build:arm64-22dfa15927f2'),
                     ('assembly', 'vyarm-board-runner:20260922')]:
    expected = json.loads(Path('/work/inputs/' + label + '-image-inspect.json').read_text())
    actual = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image]))[0]
    assert actual['Architecture'] == 'arm64', label
    assert actual['RootFS'] == expected['RootFS'], (label, 'RootFS mismatch')
    config = actual['Config'].copy()
    ignored = {}
    print(label, 'Docker-only fields:', {k: config[k] for k in set(config) - set(expected['Config'])}, flush=True)
    for key in set(config) - set(expected['Config']):
        value = config[key]
        # Legacy parent-image identity is bookkeeping, not container behavior.
        legacy_parent = key == 'Image' and isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value)
        assert legacy_parent or (key in empty_defaults and value in (None, '', False, [], {})), (label, key, value)
        ignored[key] = config.pop(key)
    assert config == expected['Config'], (label, 'Config mismatch', config)
    proof[label] = {'image_id': actual['Id'], 'architecture': actual['Architecture'],
                    'RootFS': actual['RootFS'], 'Config': config,
                    'docker_empty_defaults': ignored}
    print(label, 'layers and effective Config match; inert Docker defaults:', ignored)
Path('/work/build-environments.json').write_text(json.dumps(proof, indent=2) + '\n')
