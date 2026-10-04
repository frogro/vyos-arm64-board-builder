#!/usr/bin/python3
"""Live prototype: service print-server and shared service usb-server.
Not yet wired into release builds. CUPS administration remains in its web UI.
"""
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from vyos.config import Config
from vyos import ConfigError

ROLE = 'print-server' if 'print_server' in Path(__file__).name else 'usb-server'
ROOT = Path('/config/profile-e')

def run(*args, **kw):
    return subprocess.run(args, check=True, text=True, timeout=90, **kw)

def values(c, key):
    x = c.get(key, [])
    return [x] if isinstance(x, str) else x

def verify(c, other):
    if c is None or 'disable' in c:
        return
    clients = values(c, 'allow_client')
    if not clients:
        raise ConfigError('Set at least one allow-client network')
    for net in clients:
        if ipaddress.ip_network(net).version != 4:
            raise ConfigError('Live prototype supports IPv4 allow-client networks')
    if ROLE == 'print-server':
        if ipaddress.ip_address(c.get('listen_address', '')).version != 4:
            raise ConfigError('Set an IPv4 listen-address')
        image = c.get('image', '')
        if not re.fullmatch(r'localhost/[a-z0-9:._/-]+', image):
            raise ConfigError('Set the locally installed CUPS image')
        run('podman', 'image', 'exists', image)
        if not (ROOT/'admin-password').is_file():
            raise ConfigError('Create /config/profile-e/admin-password (mode 600) first')
    else:
        ids = values(c, 'allow_usb_id')
        if not ids or any(not re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{4}', x) for x in ids):
            raise ConfigError('Explicit allow-usb-id vvvv:pppp required')
        if not Path('/usr/local/libexec/virtualhere/vhusbdarm64').is_file():
            raise ConfigError('Install official generic VirtualHere ARM64 server first')
    # A USB printer passed to CUPS must never also be allowed by VH.
    cups = c if ROLE == 'print-server' else (other or {})
    vh = (other or {}) if ROLE == 'print-server' else c
    for port in values(cups, 'usb_port'):
        if not re.fullmatch(r'[0-9]+-[0-9]+(?:\.[0-9]+)*', port):
            raise ConfigError('Invalid physical USB port')
        dev = Path('/sys/bus/usb/devices')/port
        if not dev.exists():
            raise ConfigError('USB port is not connected: ' + port)
        ident = dev.joinpath('idVendor').read_text().strip()+':'+dev.joinpath('idProduct').read_text().strip()
        if 'disable' not in vh and ident in values(vh, 'allow_usb_id'):
            raise ConfigError('USB device selected by both CUPS and VirtualHere: '+port)

def firewall(c):
    table = 'vyarm_print' if ROLE == 'print-server' else 'vyarm_usb'
    port = 631 if ROLE == 'print-server' else 7575
    exists = subprocess.run(['nft','list','table','inet',table], capture_output=True).returncode == 0
    rules = f'delete table inet {table}\n' if exists else ''
    if c is not None and 'disable' not in c:
        nets = ', '.join(str(ipaddress.ip_network(x)) for x in values(c,'allow_client'))
        rules += f'''table inet {table} {{
 chain input {{
  type filter hook input priority -5; policy accept;
  iifname "lo" tcp dport {port} accept
  ip saddr {{ {nets} }} tcp dport {port} accept
  tcp dport {port} reject
 }}
}}
'''
    if rules:
        run('nft','-f','-',input=rules)

def apply(c):
    unit = 'vyarm-print.service' if ROLE == 'print-server' else 'vyarm-usb.service'
    run('systemctl','stop',unit)
    firewall(c)
    if c is None or 'disable' in c:
        return
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    if ROLE == 'usb-server':
        cfg = ROOT/'virtualhere.ini'
        # Preserve server-generated identity/license; never edit a running server's file.
        entries = {}
        if cfg.exists():
            for line in cfg.read_text().splitlines():
                if '=' in line:
                    k,v = line.split('=',1); entries[k] = v
        entries.update(ServerName='VyARM USB', UseAVAHI='0',
                       AllowedDevices=','.join('/'.join(f'{int(n,16):x}' for n in x.split(':')) for x in values(c,'allow_usb_id')))
        cfg.write_text(''.join(k+'='+v+'\n' for k,v in entries.items()))
        cfg.chmod(0o600)
        execstart = '/usr/local/libexec/virtualhere/vhusbdarm64 -c /config/profile-e/virtualhere.ini'
    else:
        for d in ('cups','spool','logs'):
            (ROOT/d).mkdir(exist_ok=True)
        # Start from packaged policy, retaining printer definitions separately.
        result = run('podman','run','--rm','--entrypoint','cat',c['image'],'/opt/cups-defaults/cupsd.conf',capture_output=True)
        text = result.stdout.replace('Listen localhost:631',f"Listen {c['listen_address']}:631")
        text = re.sub(r'^Browsing .*$', 'Browsing Off', text, flags=re.M)
        text = re.sub(r'^WebInterface .*$', 'WebInterface Yes', text, flags=re.M)
        acl='\n  Order allow,deny\n'+''.join('  Allow from '+str(ipaddress.ip_network(n))+'\n' for n in values(c,'allow_client'))
        text=re.sub(r'(<Location [^>]+>)',lambda m:m[1]+acl,text)
        text += '\nDefaultEncryption Required\nPreserveJobFiles No\nMaxJobs 100\nMaxRequestSize 104857600\n'
        (ROOT/'cups/cupsd.conf').write_text(text)
        devices=[]
        for port in values(c,'usb_port'):
            d=Path('/sys/bus/usb/devices')/port
            node=f"/dev/bus/usb/{int((d/'busnum').read_text()):03}/{int((d/'devnum').read_text()):03}"
            devices.extend(['--device',node])
        cmd=['/usr/bin/podman','run','--rm','--replace','--name','vyarm-print','--network','host',
             '--memory','512m','--pids-limit','256',
             '-v',str(ROOT/'cups')+':/etc/cups', '-v',str(ROOT/'spool')+':/var/spool/cups',
             '-v',str(ROOT/'logs')+':/var/log/cups',
             '-v',str(ROOT/'admin-password')+':/run/secrets/printadmin:ro',*devices,c['image']]
        execstart = ' '.join(cmd)
    Path('/run/systemd/system/'+unit).write_text(f'''[Unit]
Description=VyARM {ROLE} live prototype
After=network-online.target
[Service]
Type=simple
ExecStart={execstart}
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
''')
    run('systemctl','daemon-reload')
    run('systemctl','start',unit)

if __name__ == '__main__':
    try:
        conf=Config()
        def get(role):
            base=['service',role]
            return conf.get_config_dict(base,key_mangling=('-','_'),get_first_key=True,no_tag_node_value_mangle=True) if conf.exists(base) else None
        c=get(ROLE)
        verify(c,get('usb-server' if ROLE=='print-server' else 'print-server'))
        apply(c)
    except (ValueError, OSError, subprocess.SubprocessError, ConfigError) as e:
        print(str(e));sys.exit(1)
