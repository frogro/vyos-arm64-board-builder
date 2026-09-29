#!/usr/bin/env python3
"""Bounded overnight watchdog; restart only the pinned build container."""
import datetime, http.client, json, os, re, socket, time
from pathlib import Path
CID = os.environ['BUILD_CONTAINER_ID']
DEADLINE = int(os.environ['WATCH_DEADLINE'])
ROOT = Path('/monitor')
LOG = Path('/source/vyarm-build-nuc.log')
class UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        self.sock.connect('/var/run/docker.sock')
def api(method, path):
    c = UnixHTTP('localhost', timeout=30)
    try:
        c.request(method, '/v1.44' + path)
        r = c.getresponse(); data = r.read()
        if r.status >= 300: raise RuntimeError(f'Docker HTTP {r.status}: {data[:200]!r}')
        return json.loads(data) if data else None
    finally: c.close()
def tail():
    with LOG.open('rb') as f:
        f.seek(max(0, LOG.stat().st_size - 65536))
        return f.read().decode(errors='replace').split('VYARM_NUC_BUILD_START')[-1]
def decide(state, output, free):
    if state['Running']: return 'running'
    if state.get('Paused') or state.get('Status') not in ('exited', 'dead'): return 'manual'
    if state['ExitCode'] == 0:
        return 'complete' if 'VYARM_BROWSER_BUILD_COMPLETE' in output else 'manual'
    if free < 10 * 1024**3: return 'disk-low'
    if re.search(r'(^|\n).*\b(?:fatal )?error:|No space left on device', output): return 'compiler-or-disk-error'
    return 'retry'
def publish(status, **data):
    record = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(), status=status, **data)
    p = ROOT / 'status.tmp'; p.write_text(json.dumps(record, indent=2)+'\n'); p.replace(ROOT/'status.json')
    print(json.dumps(record), flush=True)
def main():
    retries = 0
    last_retry = 0
    started = time.monotonic()
    while time.time() < DEADLINE and time.monotonic()-started < 12*3600:
        try:
            item = api('GET', f'/containers/{CID}/json')
            if item['Id'] != CID: raise RuntimeError('Container identity mismatch')
            state = item['State']
            fs = os.statvfs('/source'); free = fs.f_bavail*fs.f_frsize
            output = tail()
            action = decide(state, output, free)
            age = max(0, time.time()-LOG.stat().st_mtime)
            if action == 'running':
                publish('running' if age < 5400 else 'no-recent-log-output', retries=retries, free_gib=round(free/1024**3,1), log_age_seconds=int(age))
            elif action == 'retry' and retries < 3:
                if time.monotonic()-last_retry < 600:
                    publish('retry-cooldown', retries=retries)
                else:
                    retries += 1
                    publish('restarting', retries=retries, exit_code=state['ExitCode'], oom=state.get('OOMKilled',False))
                    api('POST', f'/containers/{CID}/start')
                    last_retry = time.monotonic()
            else:
                publish('retry-limit' if action=='retry' else action, retries=retries, exit_code=state['ExitCode'])
                return
        except Exception as exc:
            publish('monitor-error', error=str(exc), retries=retries)
        time.sleep(120)
    publish('overnight-window-ended', retries=retries)
if __name__ == '__main__': main()
