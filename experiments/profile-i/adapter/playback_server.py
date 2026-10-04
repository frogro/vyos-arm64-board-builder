#!/usr/bin/env python3
"""Local-only player delivery independent of the Anthias management process."""
import datetime,http.server,json,mimetypes,os,re,shutil,threading,time,urllib.request
import navigation
from pathlib import Path
ROOT=Path(os.environ.get('VYARM_I_ROOT','/config/profile-i')); CACHE=ROOT/'playback'; MEDIA=CACHE/'media'; MEDIA.mkdir(parents=True,exist_ok=True)
MAX_BYTES=8*1024**3

def atomic(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj));tmp.replace(path)

def snapshot():
 try:
  return json.loads((CACHE/'playlist.json').read_text())
 except (OSError,ValueError):return {'assets':[]}

def usable(data):
 deadline=data.get('deadline')
 if deadline and datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(deadline):
  return {**data,'assets':[],'expired':True}
 return data

def refresh():
 while True:
  try:
   with urllib.request.urlopen('http://127.0.0.1:8088/i/playlist',timeout=4) as r:data=json.load(r)
   total=0; wanted=set()
   for a in data['assets']:
    if a['url'].startswith('/i/media/'):
     aid=a['id']
     if not re.fullmatch('[a-fA-F0-9]{32}',aid):raise ValueError('invalid media id')
     candidates=[p for p in (ROOT/'data/anthias_assets').glob(aid+'.*') if p.is_file()]
     if len(candidates)!=1:raise ValueError('missing/ambiguous media')
     src=candidates[0];total+=src.stat().st_size
     if total>MAX_BYTES:raise ValueError('active media exceeds 8 GiB cache limit')
     target=MEDIA/src.name
     if not target.exists():os.link(src,target)
     wanted.add(src.name);a['url']='/media/'+src.name
   data['synced_at']=time.time();atomic(CACHE/'playlist.json',data)
   for p in MEDIA.iterdir():
    if p.name not in wanted:p.unlink()
   atomic(CACHE/'sync.json',{'ok':True,'last_success':time.time(),'active_media_bytes':total,'limit_bytes':MAX_BYTES})
  except Exception as e:
   atomic(CACHE/'sync.json',{'ok':False,'error':str(e),'checked_at':time.time()})
  time.sleep(2)

class Handler(http.server.BaseHTTPRequestHandler):
 def do_POST(self):
  if self.path != '/navigate' or self.headers.get('Origin')!='http://127.0.0.1:8089':self.send_error(403);return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<2048:raise ValueError('Invalid request')
   aid=json.loads(self.rfile.read(length))['id']
   a=next(a for a in usable(snapshot())['assets'] if a['id']==aid and a['type'] in ('webpage','web'))
   if not a['url'].startswith(('http://','https://')):raise ValueError('Invalid URL')
   navigation.requests.put_nowait(a)
  except Exception as e:self.send_error(400,str(e));return
  self.send_response(202);self.end_headers()
 def do_GET(self):self.serve(False)
 def do_HEAD(self):self.serve(True)
 def serve(self,head):
  route=self.path.split('?')[0]
  if route=='/playlist':
   body=json.dumps(usable(snapshot())).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers()
   if not head:self.wfile.write(body)
   return
  if route=='/player':path=Path(__file__).parent/'player.html'
  elif route.startswith('/media/') and re.fullmatch(r'[a-fA-F0-9]{32}\.[A-Za-z0-9]+',route[7:]):path=MEDIA/route[7:]
  else:self.send_error(404);return
  try:f=path.open('rb')
  except OSError:self.send_error(404);return
  with f:
   size=os.fstat(f.fileno()).st_size;start,end=0,size-1;code=200
   value=self.headers.get('Range')
   if value:
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not match or not any(match.groups()):self.send_error(416);return
    first,last=match.groups()
    if first:start=int(first);end=min(int(last),end) if last else end
    else:start=max(0,size-int(last))
    if start>end or start>=size:self.send_error(416);return
    code=206
   self.send_response(code);self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream');self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-cache')
   if code==206:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
   self.end_headers()
   if head:return
   f.seek(start);left=end-start+1
   try:
    while left:
     b=f.read(min(left,262144))
     if not b:break
     self.wfile.write(b);left-=len(b)
   except (BrokenPipeError,ConnectionResetError):pass
 def log_message(self,*args):pass

if __name__=='__main__':
 threading.Thread(target=refresh,daemon=True).start()
 threading.Thread(target=navigation.run,daemon=True).start()
 http.server.ThreadingHTTPServer(('127.0.0.1',8089),Handler).serve_forever()
