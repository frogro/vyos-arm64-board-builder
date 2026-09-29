import os,fcntl,select,struct,time,subprocess,runpy,json,shlex
ssh=runpy.run_path('/tmp/av1-remote.py')['SSH']
p='/dev/input/by-id/usb-VyARM_Isolated_HID_test_VYARM-HID-PROBE-event-kbd'
for _ in range(50):
 if os.path.exists(p):break
 time.sleep(.1)
f=os.open(p,os.O_RDONLY|os.O_NONBLOCK)
fcntl.ioctl(f,0x40044590,1)
script='''import os,time,glob
major,minor=map(int,open('/sys/kernel/config/usb_gadget/vyarm-hid-probe/functions/hid.keyboard/dev').read().strip().split(':'))
paths=[p for p in glob.glob('/dev/hidg*') if os.major(os.stat(p).st_rdev)==major and os.minor(os.stat(p).st_rdev)==minor]
assert len(paths)==1,paths
f=os.open(paths[0],os.O_WRONLY)
for i in range(200):
 os.write(f,bytes([0,0,4,0,0,0,0,0]));time.sleep(.02)
 os.write(f,bytes(8));time.sleep(.02)
os.close(f)
print('200_PRESS_RELEASE_SENT',flush=True)
'''
proc=None;events=[];detached=False
try:
 proc=subprocess.Popen(ssh+['sudo timeout 15 python3 -'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 proc.stdin.write(script.encode());proc.stdin.close()
 end=time.monotonic()+18
 while time.monotonic()<end:
  if select.select([f],[],[],.1)[0]:
   b=os.read(f,2400)
   for off in range(0,len(b),24):
    s,u,t,c,v=struct.unpack('llHHi',b[off:off+24])
    if t==1:events.append([c,v])
  if proc.poll() is not None and len(events)>=400:break
 result={'exit':proc.wait(timeout=3),'events':events,'stdout':proc.stdout.read().decode(),'stderr':proc.stderr.read().decode()}
 result['exact_match']=events==[[30,v] for _ in range(200) for v in (1,0)]
 print(json.dumps(result),flush=True)
finally:
 r=subprocess.run(ssh+['sudo /bin/sh /run/vyarm-usba-probe-cleanup.sh'],timeout=15)
 detached=r.returncode==0
 if not detached:
  # Do not expose delayed reports to desktop while the independent timer detaches.
  time.sleep(95)
 try:fcntl.ioctl(f,0x40044590,0)
 except OSError as e:
  if e.errno != 19:raise
 finally:os.close(f)
