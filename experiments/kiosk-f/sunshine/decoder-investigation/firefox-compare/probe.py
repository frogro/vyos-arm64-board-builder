"""Bounded Firefox playback probe; logs, not frame totals, establish decoding."""
import json, os, subprocess, sys, threading
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
codec=sys.argv[1]
assert codec in ('h264','hevc')
result={}; done=threading.Event()
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory='/fixtures',**kw)
 def do_GET(self):
  if self.path.startswith('/probe.html'):
   html=Path('/fixtures/browser-decode-probe.html').read_text().replace('function save() {',"function save() { fetch('/result',{method:'POST',body:JSON.stringify(report)});")
   data=html.encode();self.send_response(200);self.send_header('Content-Type','text/html');self.end_headers();self.wfile.write(data)
  else:super().do_GET()
 def do_POST(self):
  global result
  size=int(self.headers.get('Content-Length',0));assert 0<size<2000000
  result=json.loads(self.rfile.read(size));self.send_response(204);self.end_headers()
  if result.get('state') in ('ended','error','play-error','timeout'):done.set()
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
profile=Path('/tmp/firefox-profile');profile.mkdir()
prefs={'media.autoplay.default':0,'media.autoplay.blocking_policy':0,'browser.shell.checkDefaultBrowser':False,'datareporting.policy.dataSubmissionEnabled':False}
if os.environ.get('FIREFOX_V4L2')=='1':prefs['media.ffmpeg.v4l2.enabled']=True
(profile/'user.js').write_text('\n'.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');' for k,v in prefs.items()))
env=dict(os.environ,MOZ_ENABLE_WAYLAND='1',MOZ_LOG='PlatformDecoderModule:5,FFmpegVideo:5',MOZ_LOG_FILE='/tmp/firefox-media.log')
p=subprocess.Popen(['firefox-esr','--no-remote','--profile',str(profile),'--width','1920','--height','1080',f'http://127.0.0.1:{server.server_port}/probe.html?codec={codec}&width=1920&timeout=50000'],env=env,stdout=sys.stderr,stderr=sys.stderr)
try:

 deadline=__import__('time').monotonic()+60
 while not done.wait(.5) and p.poll() is None and __import__('time').monotonic()<deadline:pass
 if not result:result={'state':'probe-failed','browserExit':p.poll()}
 print(json.dumps({'codec':codec,'prefs':prefs,'page':{k:v for k,v in result.items() if k!='frames'}},indent=2))
finally:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 for log in Path('/tmp').glob('firefox-media.log*'):
  print('\nLOG '+log.name,file=sys.stderr)
  print(log.read_text(errors='replace')[-2000000:],file=sys.stderr)
 server.shutdown()
