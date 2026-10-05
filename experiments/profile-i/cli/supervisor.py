#!/usr/bin/python3
"""Manage the I stack; playback remains available during management restarts."""
import json,os,signal,subprocess,time
from pathlib import Path
BASE=Path(os.environ.get('VYARM_I_BASE','/usr/share/vyos-arm64-board-builder/signage-runtime'))
ROOT=Path(os.environ.get('VYARM_I_ROOT','/config/profile-i'))
ADAPTER=BASE/'adapter'
stop=False

def stopping(*_):
    global stop
    stop=True

signal.signal(signal.SIGTERM,stopping)
signal.signal(signal.SIGINT,stopping)
config=json.loads(Path('/run/vyarm-signage/config.json').read_text())
meta=json.loads((BASE/'runtime.json').read_text())
os.environ['CONTAINERS_STORAGE_CONF']=str(BASE/'storage.conf')
os.environ['VYARM_I_ROOT']=str(ROOT)
os.environ['VYARM_I_KIOSK']=config['kiosk']
ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
for name in ('data','playback'):(ROOT/name).mkdir(mode=0o700,exist_ok=True)
# Pinned Anthias utilities and Channels also use redis:6379, independently of
# Celery's URL. Bind only loopback and supply the alias inside these containers.
common=['podman','run','--rm','--replace','--network','host','--add-host','redis:127.0.0.1','--cap-drop=ALL','--security-opt','no-new-privileges','--pids-limit','256']
app=common+['--memory=768m','--cpus=2','-v',str(ROOT/'data')+':/data',
    '-e','CELERY_BROKER_URL=redis://127.0.0.1:6379/0','-e','CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0',
    '-e','LISTEN=0.0.0.0','-e','PORT=8088','-e','TZ='+config.get('timezone','UTC')]
commands={
    'playback':['python3',str(ADAPTER/'playback_server.py')],
    'status':['python3',str(ADAPTER/'status_collector.py')],
    'redis':common+['--name','vyarm-signage-redis','--memory=128m','--user','65534:65534','--entrypoint','redis-server',meta['redis_tag'],
             '--bind','127.0.0.1','--port','6379','--save','','--appendonly','no'],
    'server':app+['--name','vyarm-signage-server',meta['tag'],'server'],
    'worker':app+['--name','vyarm-signage-worker',meta['tag'],'worker'],
}
processes={};retry={}
try:
    while not stop:
        for name,cmd in commands.items():
            if name=='worker' and not (ROOT/'data/.anthias/vyarm-initialized').exists():continue
            proc=processes.get(name)
            if proc and proc.poll() is not None:
                print(name,'exited',proc.returncode,flush=True)
                del processes[name];retry[name]=time.monotonic()+5
            if name not in processes and time.monotonic()>=retry.get(name,0):
                processes[name]=subprocess.Popen(cmd,start_new_session=True)
        time.sleep(.5)
finally:
    # Stop containers before signalling their attached podman process groups:
    # fuse-overlayfs can share those groups and must outlive the application.
    # Stop the worker before Redis so a graceful exit can finish its bookkeeping.
    for name in ('worker','server','redis'):
        subprocess.run(['podman','stop','--ignore','--time','15','vyarm-signage-'+name],timeout=25,check=False)
    for name in ('playback','status'):
        proc=processes.get(name)
        if proc is None:continue
        if proc.poll() is None:
            try:os.killpg(proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    for proc in processes.values():
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(proc.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            proc.wait()
