"""Initialize persistent state once; fail closed before opening HTTP."""
import os,sys,shutil,subprocess
from pathlib import Path
root=Path('/data'); config=root/'.anthias'
config.mkdir(parents=True,exist_ok=True)
(root/'anthias_assets').mkdir(exist_ok=True)
(config/'backups').mkdir(exist_ok=True)
for name in ('anthias.conf','default_assets.yml'):
    target=config/name
    if not target.exists():shutil.copyfile('/usr/src/app/ansible/roles/anthias/files/'+name,target)
if sys.argv[1]=='worker':
    os.execvp('python',['python','/opt/i/i_profile.py'])
subprocess.run(['python','-m','anthias_server.manage','migrate','--noinput'],check=True)
import django
django.setup()
from django.contrib.auth.models import User
from anthias_server.settings import settings
marker=config/'vyarm-initialized'
if not marker.exists():
    # Existing installations retain their users and passwords.
    if not User.objects.exists():User.objects.create_superuser('vyos',password='vyos')
    settings.load();settings['auth_backend']='auth_basic';settings['analytics_opt_out']=True;settings.save()
    marker.touch(mode=0o600)
os.execvp('uvicorn',['uvicorn','i_asgi:application','--host',os.getenv('LISTEN','127.0.0.1'),
                    '--port',os.getenv('PORT','8088'),'--workers','1','--timeout-keep-alive','30'])
