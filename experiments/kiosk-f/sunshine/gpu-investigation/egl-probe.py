import ctypes as C,json
E=C.CDLL('libEGL.so.1'); G=None
def f(lib,name,result,args):
 if lib is None:
  E.eglGetProcAddress.restype=C.c_void_p
  E.eglGetProcAddress.argtypes=[C.c_char_p]
  return C.CFUNCTYPE(result,*args)(E.eglGetProcAddress(name.encode()))
 fn=getattr(lib,name); fn.restype=result;fn.argtypes=args;return fn
P=C.c_void_p;I=C.c_int;U=C.c_uint
addr=f(E,'eglGetProcAddress',P,[C.c_char_p])(b'eglGetPlatformDisplayEXT')
display=C.CFUNCTYPE(P,U,P,C.POINTER(I))(addr)(0x31DD,None,None)
major=I();minor=I()
assert f(E,'eglInitialize',U,[P,C.POINTER(I),C.POINTER(I)])(display,C.byref(major),C.byref(minor))
attrs=(I*13)(0x3033,1,0x3040,4,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038)
config=P();n=I()
assert f(E,'eglChooseConfig',U,[P,C.POINTER(I),C.POINTER(P),I,C.POINTER(I)])(display,attrs,C.byref(config),1,C.byref(n)) and n.value
assert f(E,'eglBindAPI',U,[U])(0x30A0)
ctx=f(E,'eglCreateContext',P,[P,P,P,C.POINTER(I)])(display,config,None,(I*3)(0x3098,2,0x3038)); assert ctx
surface=f(E,'eglCreatePbufferSurface',P,[P,P,C.POINTER(I)])(display,config,(I*5)(0x3057,8,0x3056,8,0x3038));assert surface
assert f(E,'eglMakeCurrent',U,[P,P,P,P])(display,surface,surface,ctx)
get=f(G,'glGetString',C.c_char_p,[U]);renderer=get(0x1F01).decode()
f(G,'glClearColor',None,[C.c_float]*4)(1,0,0,1)
f(G,'glClear',None,[U])(0x4000)
pixel=(C.c_ubyte*4)()
f(G,'glReadPixels',None,[I,I,I,I,U,U,P])(0,0,1,1,0x1908,0x1401,pixel)
print(json.dumps({'renderer':renderer,'version':get(0x1F02).decode(),'pixel':list(pixel),'egl':[major.value,minor.value]}))
assert list(pixel)==[255,0,0,255]
assert 'llvmpipe' not in renderer.lower() and 'softpipe' not in renderer.lower()
