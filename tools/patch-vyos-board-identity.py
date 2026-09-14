#!/usr/bin/env python3
"""Install the E52C-tested Device Tree fallback in a staged VyOS rootfs."""
import argparse
from pathlib import Path
import re
import subprocess


def patch(rootfs):
    lib = rootfs / 'usr/lib/python3/dist-packages/vyos'
    version = lib / 'version.py'
    router = rootfs / 'usr/libexec/vyos/init/vyos-router'
    helper = Path(__file__).parent / 'common-firstboot/board_identity.py'
    source = version.read_text()
    boot = router.read_text()
    marker = '# Board identity Device Tree fallback'
    if marker in source or '_board_original_gen_duid' in boot:
        raise RuntimeError('Board identity already patched; refusing partial/double installation')
    needle = '    return version_data'
    # Restrict insertion to get_full_version_data, leaving other version helpers alone.
    start = source.index('def get_full_version_data(')
    end = source.find('\ndef ', start + 1)
    if end < 0:
        end = len(source)
    function = source[start:end]
    if function.count(needle) != 1:
        raise RuntimeError('Unexpected VyOS version function')
    addition = '''    # Board identity Device Tree fallback
    from vyos.board_identity import hardware
    try:
        fallback = hardware()
    except (OSError, ValueError, RuntimeError):
        fallback = {}
    for key, value in fallback.items():
        if version_data.get(key) in (None, '', 'Unknown'):
            version_data[key] = value
'''
    source = source[:start] + function.replace(needle, addition + needle) + source[end:]
    pattern = r'(?m)^gen_duid\s*\(\s*\)\s*\n\{\n.*?^\}'
    matches = list(re.finditer(pattern, boot, re.S))
    if len(matches) != 1 or '/sys/class/dmi/id/product_uuid' not in matches[0].group():
        raise RuntimeError('Unexpected VyOS DUID function')
    original = re.sub('^gen_duid', '_board_original_gen_duid', matches[0].group(), count=1)
    replacement = original + '''

gen_duid ()
{
    if [ -f /var/lib/dhcpv6/dhcp6c_duid ]; then
        /usr/bin/python3 -m vyos.board_identity
    elif [ -f /sys/class/dmi/id/product_uuid ] || [ -f /sys/class/dmi/id/product_serial ]; then
        _board_original_gen_duid
    else
        /usr/bin/python3 -m vyos.board_identity
    fi
}
'''
    boot = re.sub(pattern, lambda _: replacement, boot, count=1, flags=re.S)
    compile(source, str(version), 'exec')
    compile(helper.read_text(), 'board_identity.py', 'exec')
    subprocess.run(['bash', '-n'], input=boot, text=True, check=True)
    (lib / 'board_identity.py').write_text(helper.read_text())
    (lib / 'board_identity.py').chmod(0o644)
    version.write_text(source)
    router.write_text(boot)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rootfs', type=Path, required=True)
    patch(parser.parse_args().rootfs)
