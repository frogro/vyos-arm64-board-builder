#!/usr/bin/env python3
import json,subprocess,time,shutil,os,re,tempfile,signal,stat
from pathlib import Path
from container_status import snapshot
ROOT=Path(os.environ.get('VYARM_I_ROOT','/config/profile-i'))
def write_json(path,value):
 fd,name=tempfile.mkstemp(prefix='.status-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as stream:json.dump(value,stream)
  os.chmod(name,0o644)
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
def read_request(path):
 fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(fd,'r') as stream:
  st=os.fstat(stream.fileno())
  if not stat.S_ISREG(st.st_mode) or st.st_size>65536:raise ValueError('Invalid request file')
  value=json.loads(stream.read(65537))
  if not isinstance(value,dict):raise ValueError('Request must be an object')
  return value
def command(args):
 try:return json.loads(subprocess.check_output(args,text=True,timeout=8))
 except Exception as e:return {'unavailable':str(e)}
def apply_request():
 p=ROOT/'data/i-display-request.json'
 if not p.exists():return
 request={}
 try:
  request=read_request(p)
  kiosk=os.environ.get('VYARM_I_KIOSK','signage-i')
  if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}',kiosk):raise ValueError('Invalid kiosk name')
  if request.get('operation') == 'export':
   from vyos.config import Config
   conf=Config()
   cfg=conf.get_config_dict(['container','name',kiosk,'kiosk'],effective=True,key_mangling=('-', '_'),get_first_key=True)
   if not cfg:raise ValueError('Configured kiosk not found')
   from backup_settings import validate
   settings=validate({'rotation':cfg.get('rotation','0'),'output':cfg.get('output','auto'),'muted':cfg.get('audio_muted','disabled')=='enabled','schedule':cfg.get('display_schedule') or None})
   write_json(ROOT/'data/i-display-result.json',{'id':request.get('id'),'ok':True,'settings':settings})
   p.unlink(missing_ok=True)
   return
  if request.get('operation','apply') != 'apply':raise ValueError('Unknown display operation')
  rotation=request['rotation'];output=request['output']
  assert rotation in ('0','90','180','270')
  assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}',output)
  script='#!/bin/vbash\nsource /opt/vyatta/etc/functions/script-template\nconfigure\nset container name signage-i kiosk rotation ROTATION\nset container name signage-i kiosk output OUTPUT\ncommit_output=$(commit 2>&1)\ncommit_status=$?\nprintf \'%s\\n\' "$commit_output"\nif [ "$commit_status" -ne 0 ] && [[ "$commit_output" != *\'No configuration changes to commit\'* ]]; then discard; builtin exit 1; fi\nsave || builtin exit 1\nexit\n'.replace("ROTATION",rotation).replace("OUTPUT",output)
  from vyos.kiosk_schedule import validate
  schedule=request.get('schedule')
  extra=''
  if schedule is not None:
   schedule=validate(schedule)
   extra=''.join('set container name signage-i kiosk display-schedule '+k+' '+v+'\n' for k,v in schedule.items())
  else:extra='delete container name signage-i kiosk display-schedule\n'
  if 'muted' in request:
   assert isinstance(request['muted'],bool)
   extra+='set container name signage-i kiosk audio-muted '+('enabled' if request['muted'] else 'disabled')+'\n'
  script=script.replace('commit_output=',extra+'commit_output=',1)
  script=script.replace('container name signage-i ', 'container name '+kiosk+' ')
  with tempfile.NamedTemporaryFile(mode='w',suffix='.vbash',delete=False) as f:
   f.write(script);name=f.name
  try:
   os.chmod(name,0o644)
   proc=subprocess.Popen(['runuser','-u','vyos','--','/bin/vbash',name],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   try:stdout,stderr=proc.communicate(timeout=90)
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.communicate()
    raise RuntimeError('Configuration transaction timed out')
   outcome={'ok':proc.returncode==0,'output':stdout[-2000:]+stderr[-1000:]}
  finally:os.unlink(name)
 except Exception as e:outcome={'ok':False,'error':str(e)}
 outcome['id']=request.get('id')
 write_json(ROOT/'data/i-display-result.json',outcome)
 p.unlink(missing_ok=True)

while True:
 apply_request()
 disk=shutil.disk_usage(ROOT/'data')
 data={'measured_at':time.time(),'host':{'model':Path('/proc/device-tree/model').read_text().strip('\0'),'load_average':os.getloadavg(),'data_filesystem':{'total_bytes':disk.total,'free_bytes':disk.free},'storage_health':'not assessed'},'kiosk':{}}
 data['kiosk']=snapshot()
 try:data['kiosk']['last_configuration_change']=json.loads((ROOT/'data/i-display-result.json').read_text())
 except (OSError,ValueError):pass
 try:data['playback_sync']=json.loads((ROOT/'playback/sync.json').read_text())
 except Exception:pass
 write_json(ROOT/'data/i-status.json',data)
 time.sleep(10)
