"""Profile G policy for the native container owner; never reconfigure networking."""
import base64
import json
from pathlib import Path
import re
import subprocess

DEFAULTS = dict(mode='receive', method='airplay', name='VyOS-Display', output='auto', rotation='0',
                drm_device='card0', decoder='auto', resolution='1920x1080', fps='60',
                bitrate='20000', codec='auto', app='Desktop', latency='50')
CHOICES = dict(mode=('receive','pair'), method=('airplay', 'moonlight', 'miracast'), rotation=('0','90','180','270'),
               decoder=('auto','software','hardware'), codec=('auto','h264','hevc','av1'))

def settings(raw):
    if not isinstance(raw, dict) or set(raw) - (set(DEFAULTS) | {'host','wifi_interface'}):
        raise ValueError('Unknown receiver setting')
    result = dict(DEFAULTS, **raw)
    for key, value in result.items():
        if not isinstance(value, str) or not value or len(value) > 128 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid receiver ' + key)
    for key, allowed in CHOICES.items():
        if result[key] not in allowed:
            raise ValueError('Invalid receiver ' + key)
    for key, pattern in dict(name=r'[A-Za-z0-9][A-Za-z0-9 ._-]{0,62}',
                             output=r'[A-Za-z0-9_.-]+', drm_device=r'card[0-9]+',
                             host=r'[A-Za-z0-9][A-Za-z0-9.:-]*',
                             wifi_interface=r'[A-Za-z0-9][A-Za-z0-9_.-]{0,14}').items():
        if key in result and not re.fullmatch(pattern, result[key]):
            raise ValueError('Invalid receiver ' + key)
    if not re.fullmatch(r'[1-9][0-9]{2,3}x[1-9][0-9]{2,3}', result['resolution']):
        raise ValueError('Resolution must be WIDTHxHEIGHT')
    w,h = map(int, result['resolution'].split('x'))
    if w > 3840 or h > 2160:
        raise ValueError('Initial G implementation supports at most 3840x2160')
    for key, low, high in [('fps', 1, 120), ('bitrate', 1000, 100000), ('latency', 0, 500)]:
        if not result[key].isdigit() or not low <= int(result[key]) <= high:
            raise ValueError(f'{key} must be between {low} and {high}')
    if result['app'].startswith('-'):
        raise ValueError('Application name cannot be an option')
    if result['mode'] == 'pair' and result['method'] != 'moonlight':
        raise ValueError('Pairing GUI is only available for Moonlight')
    if result['method'] == 'moonlight' and result['mode'] != 'pair' and 'host' not in result:
        raise ValueError('Moonlight requires a host; pair using its GUI before streaming')
    if result['method'] == 'miracast' and 'wifi_interface' not in result:
        raise ValueError('Experimental Miracast requires a dedicated wifi-interface')
    return result

def environment(config):
    if 'receiver' not in config:
        return []
    if 'kiosk' in config:
        raise ValueError('Choose kiosk or receiver within one container')
    if any(k.startswith('G_RECEIVER') for k in config.get('environment', {})):
        raise ValueError('Remove conflicting G_RECEIVER environment overrides')
    if 'command' in config or 'arguments' in config:
        raise ValueError('Receiver owns its entrypoint; use receiver mode for pairing')
    cfg = settings(config['receiver'])
    if 'allow_host_networks' not in config or config.get('network'):
        raise ValueError('Receiver requires explicit allow-host-networks and no container network')
    volumes = list(config.get('volume', {}).values())
    if not any(v.get('destination') == '/state' and
               re.fullmatch(r'/config/[A-Za-z0-9_./-]+', v.get('source','')) and
               '..' not in Path(v['source']).parts and v.get('mode','rw') == 'rw' for v in volumes):
        raise ValueError('Receiver needs a persistent rw /config/... volume at /state')
    devices = list(config.get('device', {}).values())
    card = '/dev/dri/' + cfg['drm_device']
    if not any(d.get('source') == card and d.get('destination') == card for d in devices):
        raise ValueError('Explicit matching DRM card device grant required')
    if cfg['method'] == 'miracast' and not {'net-admin', 'net-raw'}.issubset(config.get('capability', [])):
        raise ValueError('Experimental Miracast requires explicit capabilities net-admin and net-raw')
    encoded = base64.b64encode(json.dumps(cfg).encode()).decode()
    return [f'Environment=G_RECEIVER_CONFIG="{encoded}"']

def read_command(*args):
    return subprocess.check_output(args, text=True, timeout=5)

def wifi_report(interface, sysnet=Path('/sys/class/net'), run=read_command):
    """Read-only per-PHY check, also rejects APs on sibling virtual interfaces."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,14}', interface):
        raise ValueError('Invalid wireless interface')
    node = sysnet / interface
    if not (node / 'phy80211').exists():
        raise ValueError('Selected interface is not a present wireless device')
    phy = (node / 'phy80211').resolve().name
    info = run('iw','phy',phy,'info')
    modes = info.split('Supported interface modes:',1)[-1].split('Band ',1)[0]
    if not all(re.search(r'\*\s+' + mode + r'\b', modes) for mode in ('P2P-client','P2P-GO')):
        raise ValueError('Driver does not advertise P2P-client and P2P-GO')
    siblings = [p.name for p in sysnet.iterdir() if (p/'phy80211').exists()
                and (p/'phy80211').resolve().name == phy]
    for name in siblings:
        state = json.loads(run('ip','-j','address','show','dev',name))[0]
        detail = run('iw','dev',name,'info')
        if state.get('addr_info') or state.get('master') or 'UP' in state.get('flags',[]) or re.search(r'\btype\s+(AP|P2P-GO)\b',detail):
            raise ValueError(f'{name} on {phy} is in use; select an unused dedicated radio')
    return {'interface':interface, 'phy':phy, 'siblings':siblings,
            'p2p_advertised':True, 'miracast_tested':False,
            'driver':(node/'device/driver').resolve().name,
            'phy_info':info}

def verify_image(image):
    data = json.loads(read_command('podman', 'image', 'inspect', image))
    if not data or data[0].get('Config', {}).get('Labels', {}).get('io.vyarm.receiver.version') != '1':
        raise ValueError('Load a compatible profile G runtime image before committing')

def verify_all(containers, interfaces=None, probe=wifi_report, image_probe=verify_image):
    """Prevent configured display conflicts and ownership of a routed/AP radio."""
    owners = {}
    for name, cfg in containers.get('name',{}).items():
        if 'disable' in cfg:
            continue
        if 'receiver' in cfg:
            environment(cfg)
            image_probe(cfg.get('image', ''))
            receiver = settings(cfg['receiver'])
            if receiver['method'] == 'miracast':
                report = probe(receiver['wifi_interface'])
                wireless = (interfaces or {}).get('wireless',{})
                if any(n in wireless for n in report['siblings']):
                    raise ValueError('Miracast radio is configured under interfaces wireless')
        for dev in cfg.get('device',{}).values():
            source = dev.get('source','')
            if re.fullmatch(r'/dev/dri/card[0-9]+', source):
                previous = owners.get(source)
                if previous and ('receiver' in cfg or 'receiver' in containers['name'][previous]):
                    raise ValueError(f'Display {source} is shared by {previous} and {name}; disable one')
                owners[source] = name
