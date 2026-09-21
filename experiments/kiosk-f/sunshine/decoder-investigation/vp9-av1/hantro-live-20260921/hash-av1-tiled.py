import sys,hashlib,json
w,h=1920,1080
size=w*h*3//2
hashes=[]
while True:
 b=sys.stdin.buffer.read(size)
 if not b: break
 if len(b)!=size: raise RuntimeError('partial frame')
 digest=hashlib.sha256()
 for start,height in ((0,h),(w*h,h//2)):
  for y in range(0,height,4):
   row=b[start+y*w:start+(y+4)*w]
   for dy in range(4):
    digest.update(b''.join(row[i+dy*4:i+dy*4+4] for i in range(0,len(row),16)))
 hashes.append(digest.hexdigest())
print(json.dumps(hashes))
