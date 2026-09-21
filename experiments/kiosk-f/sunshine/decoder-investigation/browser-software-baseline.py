import subprocess,json,os,select,time,sys
codec=sys.argv[1]
log=open('/tmp/chromium-probe.log','w')
p=subprocess.Popen(['bash','-c','exec 3<&0 4>&1; exec chromium --headless --disable-gpu --no-first-run --autoplay-policy=no-user-gesture-required --disable-background-networking --user-data-dir=/tmp/probe-profile --remote-debugging-pipe'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log)
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
 call('Page.navigate',{'url':'file:///fixtures/browser-decode-probe.html?codec='+codec},s)
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  time.sleep(.5)
  r=call('Runtime.evaluate',{'expression':'window.decodeProbe','returnByValue':True},s)
  value=r.get('result',{}).get('value',{})
  if value.get('state') in ['ended','error','timeout','play-error']:break
 # Let asynchronous Media diagnostics arrive after playback errors/end.
 for _ in range(3):
  time.sleep(.3)
  call('Runtime.evaluate',{'expression':'0'},s)
 support=call('Runtime.evaluate',{'expression':"({h264:document.createElement('video').canPlayType('video/mp4; codecs=\"avc1.64001f\"'),hevc:document.createElement('video').canPlayType('video/mp4; codecs=\"hvc1.1.6.L93.B0\"')})",'returnByValue':True},s)
 print(json.dumps({'page':value,'support':support.get('result',{}).get('value'), 'mediaEvents':events},indent=2))
finally:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
