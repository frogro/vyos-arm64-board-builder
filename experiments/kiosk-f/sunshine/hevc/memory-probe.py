import json, pathlib, subprocess, time
out=pathlib.Path('/probe')
results={}
for codec in ('h264','hevc'):
    log=out/f'memory-{codec}.log'
    samples=[];started=time.monotonic()
    with log.open('w') as stream:
        proc=subprocess.Popen(['/usr/local/libexec/vyarm-encode-smoke',codec+'_rkmpp',str(out/f'memory.{codec}'),'50','120','drain'],stderr=stream,stdout=stream)
        try:
            while proc.poll() is None:
                if time.monotonic()-started > 240:
                    proc.kill();raise RuntimeError('codec test timeout')
                try:
                    status=pathlib.Path(f'/proc/{proc.pid}/status').read_text()
                    rss=next(int(x.split()[1]) for x in status.splitlines() if x.startswith('VmRSS:'))
                    fds=len(list(pathlib.Path(f'/proc/{proc.pid}/fd').iterdir()))
                    cycles=log.read_text().count('Completed cycle')
                    samples.append(dict(seconds=round(time.monotonic()-started,2),rss_kib=rss,fds=fds,completed_cycles=cycles))
                except (FileNotFoundError,ProcessLookupError,StopIteration):pass
                time.sleep(0.5)
        finally:
            if proc.poll() is None:proc.kill()
            rc=proc.wait()
    text=log.read_text()
    results[codec]=dict(exit_code=rc,completed_cycles=text.count('Completed cycle'),invalid_pool_warnings=text.count('invalid mem pool'),leaked_group_warnings=text.count('cleaning leaked group'),samples=samples)
    (out/'memory-results.json').write_text(json.dumps(results,indent=2)+'\n')
    if rc or results[codec]['completed_cycles']!=50 or results[codec]['invalid_pool_warnings'] or results[codec]['leaked_group_warnings']:
        raise RuntimeError('failed lifecycle probe: '+codec)
print('Both codecs completed 50 cycles; measurements saved')
