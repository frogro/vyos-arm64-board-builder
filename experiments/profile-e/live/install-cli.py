#!/usr/bin/python3
"""Install reversible live-test templates; source file must be next to installer."""
from pathlib import Path
import shutil
import subprocess
here=Path(__file__).resolve().parent
from vyos.xml_ref.cache import reference
import json
cache=Path('/usr/lib/python3/dist-packages/vyos/xml_ref/cache.py')
backup=Path('/config/profile-e/xml-cache.before-test.py')
if not backup.exists(): shutil.copyfile(cache,backup)
supervisor=Path('/usr/local/libexec/vyarm-print-supervisor.py')
supervisor.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(here/'cups-supervisor.py',supervisor);supervisor.chmod(0o755)
updates={}
for role,fields in {
 'print-server':{'listen-address':False,'allow-client':True,'image':False,'usb-port':True,'disable':None},
 'usb-server':{'allow-client':True,'allow-usb-id':True,'disable':None},
}.items():
    owner=Path('/usr/libexec/vyos/conf_mode/service_'+role.replace('-','_')+'.py')
    shutil.copyfile(here/'service.py',owner);owner.chmod(0o755)
    def data(kind='other',multi=False,valueless=False,owner=None,priority=None):
        return {'node_type':kind,'multi':multi,'valueless':valueless,'owner':owner,'priority':priority,'default_value':None}
    updates[role]={'node_data':data(owner=str(owner),priority='1100')}
    for name,multi in fields.items():
        updates[role][name]={'node_data':data('leaf',bool(multi),multi is None)}
    root=Path('/opt/vyatta/share/vyatta-cfg/templates/service')/role
    root.mkdir(exist_ok=True)
    (root/'node.def').write_text(f'priority: 1100\nhelp: VyARM {role} live prototype\nend: sudo sh -c "${{vyshim}} {owner}"\n')
    for name,multi in fields.items():
        p=root/name;p.mkdir(exist_ok=True)
        (p/'node.def').write_text(('multi:\n' if multi else '')+('type: txt\n' if multi is not None else '')+'help: '+name+'\n')
    unit='vyarm-print' if role=='print-server' else 'vyarm-usb'
    path=Path('/run/systemd/system')/(unit+'.service')
    if not path.exists():path.write_text('[Service]\nType=oneshot\nExecStart=/bin/true\n')
cache.write_text(backup.read_text()+'\nreference["service"].update('+repr(updates)+')\n')
subprocess.run(['systemctl','restart','vyos-configd'],check=True)
subprocess.run(['systemctl','daemon-reload'],check=True)
