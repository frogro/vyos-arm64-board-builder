import gi,sys,json,hashlib,time
gi.require_version('Gst','1.0')
from gi.repository import Gst
Gst.init(None)
filename,decoder=sys.argv[1:]
p=Gst.parse_launch(f'filesrc location={filename} ! qtdemux ! h265parse ! {decoder} ! videoconvert ! video/x-raw,format=NV12 ! appsink name=s emit-signals=true sync=false')
frames=[]
def sample(s):
    x=s.emit('pull-sample');b=x.get_buffer();ok,m=b.map(Gst.MapFlags.READ)
    if not ok: return Gst.FlowReturn.ERROR
    frames.append([hashlib.sha256(m.data).hexdigest(),b.pts,b.duration,len(m.data),x.get_caps().to_string()]);b.unmap(m)
    return Gst.FlowReturn.OK
p.get_by_name('s').connect('new-sample',sample)
t=time.monotonic();p.set_state(Gst.State.PLAYING)
m=p.get_bus().timed_pop_filtered(45*Gst.SECOND,Gst.MessageType.ERROR|Gst.MessageType.EOS)
e=None if m and m.type==Gst.MessageType.EOS else str(m.parse_error()) if m else 'timeout'
p.set_state(Gst.State.NULL)
print(json.dumps(dict(seconds=time.monotonic()-t,error=e,frames=frames)))
sys.exit(bool(e))
