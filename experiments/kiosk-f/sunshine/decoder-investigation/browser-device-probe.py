from pathlib import Path
import subprocess,json,os,select,time,sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from functools import partial
from threading import Thread
server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory='/fixtures'))
Thread(target=server.serve_forever,daemon=True).start()
codec=sys.argv[1]
log=open('/tmp/chromium-probe.log','w')
# Keep Chromium's sandbox; expose devices through the disposable container.
flags=['--headless','--no-first-run','--autoplay-policy=no-user-gesture-required',
 '--disable-background-networking','--user-data-dir=/tmp/probe-profile',
 '--remote-debugging-pipe','--enable-logging=stderr']
if len(sys.argv)>2 and sys.argv[2] in ('gpu','v4l2','wayland','wayland-native'):
 flags += ['--enable-gpu','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=gles']
if len(sys.argv)>2 and sys.argv[2] in ('v4l2','wayland','wayland-native'):
 flags += ['--enable-features=AcceleratedVideoDecoder,AcceleratedVideoDecodeLinuxGL,PreferV4L2VideoAcceleration','--vmodule=*v4l2*=3,*video_decoder*=2,*gpu_mojo_media_client*=2']
if len(sys.argv)>2 and sys.argv[2] in ('wayland','wayland-native'):
 flags.remove('--headless')
 flags += ['--ozone-platform=wayland']
if len(sys.argv)>2 and sys.argv[2]=='wayland-native':
 flags.remove('--ignore-gpu-blocklist')
if os.environ.get('PROBE_PERF') == '1':
 flags=[f for f in flags if not f.startswith('--vmodule=')]
 flags += ['--start-fullscreen', '--window-size='+os.environ.get('PROBE_WIDTH','1920')+','+os.environ.get('PROBE_HEIGHT','1080')]
p=subprocess.Popen(['bash','-c','exec 3<&0 4>&1; exec chromium "$@"','probe',*flags],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)

buf=b''; seq=0; events=[]
def receive(deadline):
 global buf
 while b'\0' not in buf:
  remaining=deadline-time.monotonic()
  if remaining<=0 or not select.select([p.stdout],[],[],remaining)[0]: raise TimeoutError()
  chunk=os.read(p.stdout.fileno(),65536)
  if not chunk: raise RuntimeError('Browser exited')
  buf+=chunk
 raw,buf=buf.split(b'\0',1)
 return json.loads(raw)
def call(method,params={},session=None):
 global seq
 seq+=1; req={'id':seq,'method':method,'params':params}
 if session:req['sessionId']=session
 p.stdin.write(json.dumps(req).encode()+b'\0');p.stdin.flush()
 deadline=time.monotonic()+15
 while True:
  r=receive(deadline)
  if r.get('id')==seq:
   if 'error' in r:raise RuntimeError(r)
   return r.get('result',{})
  if r.get('method','').startswith('Media.'):events.append(r)
try:
 target=call('Target.createTarget',{'url':'about:blank'})['targetId']
 s=call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
 call('Media.enable',session=s)
 call('Page.enable',session=s)
 call('Page.navigate',{'url':'http://127.0.0.1:'+str(server.server_port)+'/browser-decode-probe.html?codec='+codec+'&timeout='+str(int(float(os.environ.get('PROBE_TIMEOUT','20'))*1000))+'&width='+os.environ.get('PROBE_WIDTH','640')},s)
 deadline=time.monotonic()+float(os.environ.get('PROBE_TIMEOUT', '20'))
 samples=[]
 while time.monotonic()<deadline:
  time.sleep(.5)
  r=call('Runtime.evaluate',{'expression':'window.decodeProbe','returnByValue':True},s)
  value=r.get('result',{}).get('value',{})
  try:
   cpu=dict(line.split() for line in Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines())
   samples.append({'monotonic':time.monotonic(),'usage_usec':int(cpu['usage_usec']),'state':value.get('state')})
  except (OSError,KeyError,ValueError): pass
  if value.get('state') in ['ended','error','timeout','play-error']:break
 # Let asynchronous Media diagnostics arrive after playback errors/end.
 for _ in range(3):
  time.sleep(.3)
  call('Runtime.evaluate',{'expression':'0'},s)
 support=call('Runtime.evaluate',{'expression':"({h264:document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.64001f\"'),hevc:document.createElement('video').canPlayType('video/mp4; codecs=\"hvc1.1.6.L93.B0\"')})",'returnByValue':True},s)
 frame=call('Runtime.evaluate',{'expression':"""(() => { const v=document.querySelector('video'); if (!v.videoWidth || v.readyState<2) return null; const c=document.createElement('canvas'); c.width=v.videoWidth;c.height=v.videoHeight;const x=c.getContext('2d');x.drawImage(v,0,0);return c.toDataURL('image/png'); })()""",'returnByValue':True},s).get('result',{}).get('value')
 gpu=call('SystemInfo.getInfo')
 print(json.dumps({'cpuSamples':samples,'finalFramePNG':frame,'flags':flags,'gpu':gpu,'page':value,'support':support.get('result',{}).get('value'), 'mediaEvents':events},indent=2))
finally:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 log.close()
 print(Path('/tmp/chromium-probe.log').read_text()[-128000:],file=sys.stderr)
