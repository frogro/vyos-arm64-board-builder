from pathlib import Path
import time,json,subprocess,sys
root=Path(sys.argv[1]);seconds=int(sys.argv[2]);assert 1<=seconds<=700
end=time.monotonic()+seconds
with (root/'memory-samples.jsonl').open('x',buffering=1) as log:
 while time.monotonic()<end:
  for codec in ['h264','hevc']:
   try:
    cid=(root/(codec+'-container-id')).read_text().strip()
    pid=int(subprocess.check_output(['podman','inspect','--format','{{.State.Pid}}',cid],stderr=subprocess.DEVNULL))
    if pid<=0:continue
    cg=next(x.split(':',2)[2] for x in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if x.startswith('0::'))
    base=Path('/sys/fs/cgroup')/cg.lstrip('/')
    record={'time':time.time(),'codec':codec,'memoryCurrent':int((base/'memory.current').read_text()),'memoryPeak':int((base/'memory.peak').read_text())}
    record['thermalZones']={}
    for zone in Path('/sys/class/thermal').glob('thermal_zone*'):
     try:record['thermalZones'][zone.name]={'type':(zone/'type').read_text().strip(),'milliCelsius':int((zone/'temp').read_text())}
     except (OSError,ValueError):pass
    log.write(json.dumps(record)+'\n')
   except (OSError,ValueError,StopIteration,subprocess.CalledProcessError):pass
  time.sleep(15)
