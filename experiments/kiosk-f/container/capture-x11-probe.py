import ctypes as c,sys,time
x=c.CDLL('libX11.so.6')
x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=c.c_void_p
d=x.XOpenDisplay(None)
if not d: raise SystemExit('Cannot open X display')
x.XDefaultRootWindow.argtypes=[c.c_void_p];x.XDefaultRootWindow.restype=c.c_ulong
root=x.XDefaultRootWindow(d)
class XImage(c.Structure):
 _fields_=[('width',c.c_int),('height',c.c_int),('xoffset',c.c_int),('format',c.c_int),('data',c.c_void_p),('byte_order',c.c_int),('bitmap_unit',c.c_int),('bitmap_bit_order',c.c_int),('bitmap_pad',c.c_int),('depth',c.c_int),('bytes_per_line',c.c_int),('bits_per_pixel',c.c_int),('red_mask',c.c_ulong),('green_mask',c.c_ulong),('blue_mask',c.c_ulong)]
x.XGetImage.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_ulong,c.c_int];x.XGetImage.restype=c.POINTER(XImage)
x.XDestroyImage.argtypes=[c.POINTER(XImage)]
for i in range(60):
 im=x.XGetImage(d,root,0,0,1920,1080,c.c_ulong(-1).value,2)
 if not im:raise SystemExit('Capture failed')
 v=im.contents
 if (v.bits_per_pixel,v.bytes_per_line,v.byte_order,v.red_mask)!=(32,7680,0,0xff0000):raise SystemExit('Unexpected pixel layout')
 sys.stdout.buffer.write(c.string_at(v.data,v.bytes_per_line*v.height));sys.stdout.buffer.flush()
 x.XDestroyImage(im)
