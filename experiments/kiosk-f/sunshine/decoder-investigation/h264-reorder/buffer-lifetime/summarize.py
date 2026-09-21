"""QBUF/DQBUF timing includes scheduling and reference retention, not pure decode."""
import re,json,sys,statistics,csv
from pathlib import Path
pat=re.compile(r'\s(\d+\.\d+): (v4l2_[qd]q?buf|v4l2_qbuf|v4l2_dqbuf): minor = 2, index = (\d+), type = (VIDEO_\w+)')
def summary(values):
 values=sorted(values)
 if not values:return {'count':0}
 return {'count':len(values),'median_ms':statistics.median(values)*1000,'p95_ms':values[int((len(values)-1)*.95)]*1000,'max_ms':max(values)*1000}
for arg in sys.argv[1:]:
 events=[]
 for line in Path(arg).read_text().splitlines():
  m=pat.search(line)
  if m:events.append((float(m[1]),m[2],int(m[3]),m[4]))
 if Path(arg).suffix=='.csv':
  with open(arg) as f:events=[(float(r['time']),r['event'],int(r['index']),r['type']) for r in csv.DictReader(f)]
 events.sort(); queued={};dequeued={};held=[];cycle=[];counts={};gaps=[];last=None
 for t,event,index,kind in events:
  if kind!='VIDEO_CAPTURE_MPLANE':continue
  counts[event]=counts.get(event,0)+1
  if event=='v4l2_qbuf':
   if index in dequeued:held.append(t-dequeued.pop(index))
   queued[index]=t
   if last is not None:gaps.append(t-last)
   last=t
  else:
   if index in queued:cycle.append(t-queued.pop(index))
   dequeued[index]=t
 print(json.dumps({'file':Path(arg).name,'captureEvents':counts,'dequeue_to_requeue':summary(held),'queue_to_dequeue':summary(cycle),'submission_gaps':summary(gaps)},indent=2))
