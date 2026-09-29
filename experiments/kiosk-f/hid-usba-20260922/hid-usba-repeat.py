import subprocess,runpy,pathlib,json,time
ssh=runpy.run_path('/tmp/av1-remote.py')['SSH']
out=pathlib.Path('/tmp/vyarm-usba-recognition-20260922')
for n in range(3):
 subprocess.run(ssh+['sudo systemctl stop vyarm-usba-safe-restore.timer'],check=True)
 subprocess.run(['python3','/tmp/av1-remote.py'],input=pathlib.Path('/tmp/hid-usba-default-setup.sh').read_bytes(),check=True)
 time.sleep(2)
 s=subprocess.check_output(ssh+['sudo bash -c '+__import__('shlex').quote('cat /sys/class/udc/fc000000.usb/state /sys/class/udc/fc000000.usb/current_speed /sys/kernel/config/usb_gadget/vyarm-hid-probe/functions/hid.keyboard/no_out_endpoint')]).decode()
 r=subprocess.run(['sudo','-n','python3','/tmp/hid-usba-capture.py'],capture_output=True,timeout=135)
 (out/f'reenumerate-{n}.json').write_bytes(r.stdout)
 (out/f'reenumerate-{n}.state').write_text(s+r.stderr.decode())
 x=json.loads(r.stdout);print(n,s.strip().replace('\n',','),'exact_match',x['exact_match'],flush=True)
 if r.returncode or not x['exact_match']:break
subprocess.run(ssh+['sudo systemctl stop vyarm-usba-safe-restore.timer'])
