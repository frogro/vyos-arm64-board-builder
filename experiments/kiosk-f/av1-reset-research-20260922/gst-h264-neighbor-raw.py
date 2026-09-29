# Isolated measurement: GStreamer C ABI via ctypes, no Python GI dependency.
import ctypes as C, json, time
from ctypes.util import find_library
G=C.CDLL(find_library('gstreamer-1.0')); O=C.CDLL(find_library('gobject-2.0')); L=C.CDLL(find_library('glib-2.0'))
def api(lib,name,result,args):
 f=getattr(lib,name); f.restype=result; f.argtypes=args; return f
ptr=C.c_void_p; text=C.c_char_p
api(G,'gst_init',None,[ptr,ptr])(None,None)
parse=api(G,'gst_parse_launch',ptr,[text,C.POINTER(ptr)])
state=api(G,'gst_element_set_state',C.c_int,[ptr,C.c_int])
busget=api(G,'gst_element_get_bus',ptr,[ptr])
wait=api(G,'gst_bus_timed_pop_filtered',ptr,[ptr,C.c_uint64,C.c_uint])
lookup=api(G,'gst_bin_get_by_name',ptr,[ptr,text])
get=api(O,'g_object_get',None,[ptr,text])
string=api(G,'gst_structure_to_string',ptr,[ptr])
free=api(L,'g_free',None,[ptr])
structurefree=api(G,'gst_structure_free',None,[ptr])
unref=api(G,'gst_object_unref',None,[ptr]); miniunref=api(G,'gst_mini_object_unref',None,[ptr])
err=ptr(); pipeline=parse(b'filesrc location=/fixtures/neighbor.h264 ! h264parse ! v4l2slh264dec ! fakesink name=measure sync=true',C.byref(err))
if err or not pipeline: raise RuntimeError('Pipeline creation failed')
bus=busget(pipeline); sink=lookup(pipeline,b'measure'); msg=None; stats=ptr()
try:
 start=time.monotonic(); started=state(pipeline,4)
 # Only EOS passes this filter. On errors, timeout fails the test; stderr retains diagnostics.
 msg=wait(bus,150_000_000_000,1)
 elapsed=time.monotonic()-start
 get(sink,b'stats',C.byref(stats),ptr())
 raw=string(stats); detail=C.string_at(raw).decode(); free(raw)
 print(json.dumps({'eos':bool(msg),'state_change':started,'elapsed_seconds':elapsed,'sink_stats':detail}),flush=True)
 if not msg: raise RuntimeError('No EOS within 150 seconds')
 import re
 assert re.search(r'rendered=\(guint64\)7200(?:[,;]|$)',detail), detail
finally:
 state(pipeline,1)
 if msg: miniunref(msg)
 if stats: structurefree(stats)
 unref(sink); unref(bus); unref(pipeline)
