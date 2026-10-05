#!/usr/bin/python3
"""Native media administration owner. F retains browser/display ownership."""
import ipaddress,json,os,re,subprocess
from pathlib import Path
from vyos.config import Config
from vyos import ConfigError
BASE=Path('/usr/share/vyos-arm64-board-builder/signage-runtime')
RUNTIME=Path('/run/vyarm-signage/config.json')
UNIT='vyarm-signage.service'

def run(*args,**kw):
    return subprocess.run(args,check=True,text=True,timeout=120,**kw)

def get_config(config=None):
    conf=config or Config()
    if not conf.exists(['service','signage']):return None
    c=conf.get_config_dict(['service','signage'],key_mangling=('-', '_'),get_first_key=True,no_tag_node_value_mangle=True)
    name=c.get('kiosk','')
    item=conf.get_config_dict(['container','name',name],key_mangling=('-', '_'),get_first_key=True) if name and conf.exists(['container','name',name]) else {}
    c['_kiosk']=item.get('kiosk',{})
    c['_host_network']='allow_host_networks' in item
    c['_image']=item.get('image','')
    return c

def verify(c):
    if c is None or 'disable' in c:return
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}',c.get('kiosk','')):raise ConfigError('Select an existing kiosk container')
    if not c.get('_host_network'):raise ConfigError('Selected kiosk requires allow-host-networks to reach the local player')
    kiosk=c['_kiosk']
    if kiosk.get('url')!='http://127.0.0.1:8089/player' or kiosk.get('display_backend')!='wayland':
        raise ConfigError('Selected kiosk requires Wayland and URL http://127.0.0.1:8089/player')
    nets=c.get('allow_client',[])
    if isinstance(nets,str):nets=[nets]
    if not nets:raise ConfigError('Set at least one allow-client IPv4 network')
    try:
        for net in nets:
            if ipaddress.ip_network(net).version!=4:raise ValueError()
    except ValueError:raise ConfigError('Invalid allow-client IPv4 network')
    if not (BASE/'runtime.json').is_file():raise ConfigError('Profile I offline runtime is missing')
    env=dict(os.environ,CONTAINERS_STORAGE_CONF=str(BASE/'storage.conf'))
    meta=json.loads((BASE/'runtime.json').read_text())
    result=subprocess.run(['podman','image','inspect',c['_image']],env=env,capture_output=True,text=True,check=True,timeout=10)
    image=json.loads(result.stdout)[0]
    labels=image.get('Labels') or image.get('Config',{}).get('Labels',{}) or {}
    if labels.get('io.vyarm.kiosk.display-controls')!='1':raise ConfigError('Select the current kiosk image with media player support')
    for key in ('tag','redis_tag'):
        if subprocess.run(['podman','image','exists',meta[key]],env=env).returncode:raise ConfigError('Profile I image import has not completed')

def generate(c):pass

def firewall_rules(c, exists=False):
    rules='delete table inet vyarm_signage\n' if exists else ''
    if c is not None and 'disable' not in c:
        nets=c['allow_client'];nets=[nets] if isinstance(nets,str) else nets
        clients=', '.join(str(ipaddress.ip_network(n)) for n in nets)
        rules+='''table inet vyarm_signage {
 chain input {
  type filter hook input priority -5; policy accept;
  iifname "lo" tcp dport 8088 accept
  ip saddr { '''+clients+''' } tcp dport 8088 accept
  tcp dport 8088 reject
 }
}
'''
    return rules

def apply(c):
    exists=subprocess.run(['nft','list','table','inet','vyarm_signage'],capture_output=True).returncode==0
    rules=firewall_rules(c,exists)
    if rules:run('nft','--check','-f','-',input=rules)
    run('systemctl','stop',UNIT)
    if rules:run('nft','-f','-',input=rules)
    if c is None or 'disable' in c:
        RUNTIME.unlink(missing_ok=True);return
    RUNTIME.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    RUNTIME.write_text(json.dumps({k:v for k,v in c.items() if not k.startswith('_')}));RUNTIME.chmod(0o600)
    run('systemctl','start',UNIT)

if __name__=='__main__':
    try:c=get_config();verify(c);generate(c);apply(c)
    except (ConfigError,ValueError,OSError,subprocess.SubprocessError) as error:
        print(error);raise SystemExit(1)
