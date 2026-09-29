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

import hashlib
src=parse(b'v4l2src device=/dev/video0 num-buffers=10 ! video/x-raw,format=BGR,width=1920,height=1080,framerate=60/1 ! appsink name=input sync=false max-buffers=2 drop=false',None)
inp=get(src,b'input')
pipes=[]
for threads in (1,4):
 p=parse(f'appsrc name=output format=time ! videoconvert n-threads={threads} ! video/x-raw,format=NV12 ! appsink name=result sync=false'.encode(),None)
 pipes.append((p,get(p,b'output'),get(p,b'result')))
 state(p,4)
state(src,4)
try:
 for n in range(10):
  sample=pull(inp,5_000_000_000); assert sample
  b=buf(sample); hashes=[]
  for index,(p,out,result) in enumerate(pipes):
   setcaps(out,caps(sample))
   if index:
    nb=alloc(None,size(b),None); m=Map(); d=Map()
    assert bmap(b,C.byref(m),1) and bmap(nb,C.byref(d),2)
    memcpy(d.data,m.data,m.size)
    assert C.string_at(m.data,m.size)==C.string_at(d.data,d.size)
    bunmap(nb,C.byref(d)); bunmap(b,C.byref(m)); assert copy(nb,b,7,0,S(-1).value)
   else: nb=ref(b)
   assert push(out,nb)==0
   output=pull(result,5_000_000_000); assert output
   ob=buf(output); m=Map(); assert bmap(ob,C.byref(m),1)
   hashes.append(hashlib.sha256(C.string_at(m.data,m.size)).hexdigest())
   bunmap(ob,C.byref(m)); samplefree(output)
  assert hashes[0]==hashes[1], hashes
  samplefree(sample)
 print('PIXEL_EQUALITY_OK: 10 identical input frames, direct/1-thread versus cached-copy/4-thread NV12 byte-for-byte equal')
finally:
 state(src,1)
 for p,o,r in pipes: state(p,1)
