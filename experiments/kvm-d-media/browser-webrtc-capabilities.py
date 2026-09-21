import subprocess,json,os,select,time,sys
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
 session=call('Target.attachToTarget',{'targetId':target,'flatten':True})['sessionId']
 expression="""(async () => {
 const capabilities=RTCRtpReceiver.getCapabilities('video');
 const pc=new RTCPeerConnection({iceServers:[]});
 pc.addTransceiver('video',{direction:'recvonly'});
 const offer=await pc.createOffer(); pc.close();
 return {capabilities,sdp:offer.sdp,userAgent:navigator.userAgent};
 })()"""
 r=call('Runtime.evaluate',{'expression':expression,'awaitPromise':True,'returnByValue':True},session)
 print(json.dumps(r,indent=2))

finally:
 p.terminate()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
