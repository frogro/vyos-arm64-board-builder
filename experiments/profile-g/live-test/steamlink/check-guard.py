import ctypes,json,concurrent.futures
class Addr(ctypes.Structure): pass
P=ctypes.POINTER(Addr)
Addr._fields_=[('next',P),('name',ctypes.c_char_p),('flags',ctypes.c_uint),('addr',ctypes.c_void_p),('mask',ctypes.c_void_p),('broad',ctypes.c_void_p),('data',ctypes.c_void_p)]
l=ctypes.CDLL(None)
l.getifaddrs.argtypes=[ctypes.POINTER(P)];l.freeifaddrs.argtypes=[P]
def run(_):
 p=P();assert l.getifaddrs(ctypes.byref(p))==0
 cur=p;out=[]
 while cur:
  a=cur.contents;out.append([a.name.decode(),ctypes.c_ushort.from_address(a.addr).value if a.addr else None]);cur=a.next
 l.freeifaddrs(p)
 return out
first=run(0)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(run,range(1000)):assert result==first
print(json.dumps(first))
