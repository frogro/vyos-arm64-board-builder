#!/usr/bin/python3
import gi,json,sys,time
gi.require_version('Gst','1.0')
from gi.repository import Gst,GLib
Gst.init(None)
p=Gst.parse_launch('filesrc location=/fixtures/test-h264.mp4 ! qtdemux ! h264parse ! v4l2slh264dec name=hw ! fakesink sync=true')
loop=GLib.MainLoop(); out={'frames':0,'decoder':'v4l2slh264dec','state':'starting'}; started=time.monotonic()
def count(pad,info):
 out['frames']+=1
 return Gst.PadProbeReturn.OK
p.get_by_name('hw').get_static_pad('src').add_probe(Gst.PadProbeType.BUFFER,count)
def msg(bus,m):
 if m.type==Gst.MessageType.ERROR:
  err,dbg=m.parse_error();out.update(state='error',error=str(err),debug=dbg);loop.quit()
 elif m.type==Gst.MessageType.EOS:out['state']='eos';loop.quit()
def deadline():
 out['state']='timeout';loop.quit();return False
bus=p.get_bus();bus.add_signal_watch();bus.connect('message',msg)
GLib.timeout_add_seconds(140,deadline)
p.set_state(Gst.State.PLAYING)
try:loop.run()
finally:p.set_state(Gst.State.NULL)
out['elapsed']=time.monotonic()-started;print(json.dumps(out),flush=True)
sys.exit(0 if out['state']=='eos' and out['frames']==7200 else 1)
