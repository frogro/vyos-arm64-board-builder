import ctypes as C, time, sys, json
G=C.CDLL('libgstreamer-1.0.so.0'); A=C.CDLL('libgstapp-1.0.so.0'); L=C.CDLL('libc.so.6')
P=C.c_void_p; I=C.c_int; U=C.c_uint; S=C.c_size_t; Q=C.c_uint64
class Map(C.Structure):
 _fields_=[('memory',P),('flags',I),('data',P),('size',S),('maxsize',S),('user_data',P*4),('reserved',P*4)]
def fn(lib,name,ret,args):
 f=getattr(lib,name); f.restype=ret; f.argtypes=args; return f
init=fn(G,'gst_init',None,[P,P]); init(None,None)
parse=fn(G,'gst_parse_launch',P,[C.c_char_p,P]); get=fn(G,'gst_bin_get_by_name',P,[P,C.c_char_p]); state=fn(G,'gst_element_set_state',I,[P,I]); unref=fn(G,'gst_object_unref',None,[P])
pull=fn(A,'gst_app_sink_try_pull_sample',P,[P,Q]); push=fn(A,'gst_app_src_push_buffer',I,[P,P]); eos=fn(A,'gst_app_src_end_of_stream',I,[P]); setcaps=fn(A,'gst_app_src_set_caps',None,[P,P])
buf=fn(G,'gst_sample_get_buffer',P,[P]); caps=fn(G,'gst_sample_get_caps',P,[P]); samplefree=fn(G,'gst_sample_unref',None,[P]); ref=fn(G,'gst_buffer_ref',P,[P]); alloc=fn(G,'gst_buffer_new_allocate',P,[P,S,P]); size=fn(G,'gst_buffer_get_size',S,[P]); bmap=fn(G,'gst_buffer_map',I,[P,C.POINTER(Map),I]); bunmap=fn(G,'gst_buffer_unmap',None,[P,C.POINTER(Map)]); copy=fn(G,'gst_buffer_copy_into',I,[P,P,U,S,S]); memcpy=fn(L,'memcpy',P,[P,P,S]); busget=fn(G,'gst_element_get_bus',P,[P]); wait=fn(G,'gst_bus_timed_pop_filtered',P,[P,Q,U])
frames=int(__import__('os').environ.get('TEST_FRAMES','120')); mode=sys.argv[1]; threads=int(sys.argv[2]); enc=len(sys.argv)>3
src=parse(('v4l2src device=/dev/video0 num-buffers={frames} ! video/x-raw,format=BGR,width=1920,height=1080,framerate=60/1 ! appsink name=input sync=false max-buffers=2 drop=false'.format(frames=frames)).encode(),None)
desc=f'appsrc name=output format=time block=true max-bytes=12441600 ! videoconvert n-threads={threads} ! video/x-raw,format=NV12'
if enc: desc+=' ! mpph264enc bps=8000000 gop=60 ! h264parse'
dst=parse((desc+' ! fakesink name=verified sync=false signal-handoffs=true').encode(),None)
received=[0]
CALLBACK=C.CFUNCTYPE(None,P,P,P,P)
@CALLBACK
def handoff(sink,buffer,pad,data): received[0]+=1
sink=get(dst,b'verified')
connect=fn(C.CDLL('libgobject-2.0.so.0'),'g_signal_connect_data',C.c_ulong,[P,C.c_char_p,CALLBACK,P,P,I])
connect(sink,b'handoff',handoff,None,None,0)
inp=get(src,b'input'); out=get(dst,b'output'); bus=busget(dst); total=0.; count=0; start=time.monotonic()
try:
 state(dst,4); state(src,4)
 for n in range(frames):
  sample=pull(inp,5_000_000_000)
  if not sample: raise RuntimeError('capture timeout/EOS before 120 frames')
  if n==0: setcaps(out,caps(sample))
  b=buf(sample)
  if mode=='copy':
   t=time.monotonic(); nb=alloc(None,size(b),None); m=Map(); d=Map()
   assert bmap(b,C.byref(m),1) and bmap(nb,C.byref(d),2)
   memcpy(d.data,m.data,m.size); bunmap(nb,C.byref(d)); bunmap(b,C.byref(m))
   assert copy(nb,b,7,0,S(-1).value)
   total+=time.monotonic()-t
  else: nb=ref(b)
  result=push(out,nb); samplefree(sample)
  if result!=0: raise RuntimeError(f'push failed {result}')
  count+=1
 eos(out); msg=wait(bus,10_000_000_000,3)
 if not msg: raise RuntimeError('output did not drain')
 # GstMessage type is available via its public type-name formatter.
 name=fn(G,'gst_message_get_structure',P,[P])(msg)
 if name: raise RuntimeError('unexpected structured message instead of EOS')
 assert received[0]==count, (received,count)
 elapsed=time.monotonic()-start
 print(json.dumps(dict(mode=mode,threads=threads,encoder=enc,frames=count,output_frames=received[0],seconds=elapsed,fps=count/elapsed,copy_seconds=total)),flush=True)
finally:
 state(src,1); state(dst,1)
 for obj in (inp,out,bus,sink,src,dst): unref(obj)
