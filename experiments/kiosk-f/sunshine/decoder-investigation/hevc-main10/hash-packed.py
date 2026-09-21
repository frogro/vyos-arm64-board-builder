import sys,hashlib,json
size=3888000; hashes=[]
while True:
 data=sys.stdin.buffer.read(size)
 if not data:break
 assert len(data)==size,len(data)
 hashes.append(hashlib.sha256(data).hexdigest())
expected=json.load(open(sys.argv[1]))['hashes']
print(json.dumps({'frames':len(hashes),'allFramesMatch':hashes==expected,'mismatchIndices':[i for i,(a,b) in enumerate(zip(hashes,expected)) if a!=b]},indent=2))

assert hashes == expected, "Frame count or pixel hash mismatch"
