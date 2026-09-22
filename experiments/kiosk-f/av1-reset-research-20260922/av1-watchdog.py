#!/usr/bin/python3
# Temporary experiment guard. Stop with SIGTERM to disarm and restore timeout.
import os,fcntl,array,signal,time,pathlib
r=pathlib.Path('/sys/class/watchdog/watchdog0')
assert (r/'state').read_text().strip()=='inactive'
assert (r/'nowayout').read_text().strip()=='0'
original=int((r/'timeout').read_text())
stopping=False
def stop(*_):
 global stopping
 stopping=True
signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
fd=os.open('/dev/watchdog0',os.O_WRONLY|os.O_CLOEXEC)
t=array.array('i',[30]);fcntl.ioctl(fd,0xc0045706,t,True)
print('ARMED timeout='+str(t[0]),flush=True)
end=time.monotonic()+480
while not stopping and time.monotonic()<end:
 os.write(fd,b'.');time.sleep(2)
if stopping:
 t=array.array('i',[original]);fcntl.ioctl(fd,0xc0045706,t,True)
 os.write(fd,b'V');os.close(fd)
 print('DISARMED original_timeout='+str(t[0]),flush=True)
else:
 print('GUARD DEADLINE: no more keepalives',flush=True)
 # Keep descriptor open. A hung test must not be disarmed by normal close.
 while True:time.sleep(2)
