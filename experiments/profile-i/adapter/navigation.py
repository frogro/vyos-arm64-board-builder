"""Bounded top-level navigation in the existing F browser, same decode policy."""
import os,json,queue,time,urllib.request,urllib.parse,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'vendor'))
import websocket
requests=queue.Queue(maxsize=1)
PLAYER='http://127.0.0.1:8089/player'
ROOT=Path(os.environ.get('VYARM_I_ROOT','/config/profile-i'))/'playback'

def report(value):
 p=ROOT/'navigation.json';t=p.with_suffix('.tmp');t.write_text(json.dumps(value));t.replace(p)

def call(ws,method,params=None):
 call.counter+=1;i=call.counter;ws.send(json.dumps({'id':i,'method':method,'params':params or {}}))
 while True:
  response=json.loads(ws.recv())
  if response.get('id')==i:
   if 'error' in response:raise RuntimeError(str(response['error']))
   return response.get('result',{})
call.counter=0

def pages():
 with urllib.request.urlopen('http://127.0.0.1:9225/json',timeout=3) as r:return json.load(r)

def recover():
 try:state=json.loads((ROOT/'navigation.json').read_text())
 except (OSError,ValueError):return
 if not state.get('active'):return
 ws=None
 try:
  target=next((p for p in pages() if p.get('id')==state.get('target_id')),None)
  if target:
   ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=5,suppress_origin=True)
   call(ws,'Page.navigate',{'url':PLAYER+'?after='+urllib.parse.quote(state['asset'])})
  report({**state,'active':False,'recovered_at':time.time()})
 except Exception:pass  # Browser may itself still be restarting; retry while idle.
 finally:
  if ws:ws.close()

def run():
 recover()
 while True:
  try:a=requests.get(timeout=2)
  except queue.Empty:
   recover();continue
  ws=None;state={'active':False,'asset':a['id']}
  try:
   target=next(p for p in pages() if p['type']=='page' and p['url'].startswith(PLAYER))
   ws=websocket.create_connection(target['webSocketDebuggerUrl'],timeout=5,suppress_origin=True)
   state.update(active=True,target_id=target['id'],url=a['url'],started_at=time.time())
   report(state)  # Durable before leaving the player, for process-crash recovery.
   result=call(ws,'Page.navigate',{'url':a['url']})
   if result.get('errorText'):raise RuntimeError(result['errorText'])
   deadline=time.monotonic()+min(3600,max(1,float(a['duration'])))
   while time.monotonic()<deadline:
    time.sleep(.2)
    try:
     playlist=json.loads((ROOT/'playlist.json').read_text())
     if not any(x['id']==a['id'] for x in playlist['assets']):break
    except (OSError,ValueError):pass
  except Exception as e:state['error']=str(e)
  finally:
   if ws:
    try:
     call(ws,'Page.navigate',{'url':PLAYER+'?after='+urllib.parse.quote(a['id'])})
     state.update(active=False,returned_at=time.time())
    except Exception as e:state['return_error']=str(e)
    ws.close()
   report(state)
   requests.task_done()
