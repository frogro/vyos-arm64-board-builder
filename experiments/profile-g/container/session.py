#!/usr/bin/env python3
"""G compositor and receiver lifecycle, reusing F's output transform and audio."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import signal
import select
import subprocess
import sys
import time
sys.path.insert(0,'/opt/profile-g')
from backend import config, command, receiver_environment
from receiver import wifi_report

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value

def main():
    cfg=config(); children=[]; stopping=False
    def stop(*_):
        nonlocal stopping
        stopping=True
    for sig in (signal.SIGTERM,signal.SIGINT): signal.signal(sig,stop)
    def launch(args,**kw):
        proc=subprocess.Popen(args,start_new_session=True,**kw);children.append(proc);return proc
    def wait_ready(test, proc, description):
        for _ in range(100):
            if stopping or proc.poll() is not None: raise RuntimeError(description+' stopped')
            if test(): return
            time.sleep(.1)
        raise RuntimeError(description+' startup timeout')
    user=pwd.getpwnam('kiosk')
    state=Path('/state'); runtime=Path('/run/receiver');runtime.mkdir(mode=0o700,exist_ok=True)
    for path in (state,runtime,state/'config',state/'cache'):
        path.mkdir(exist_ok=True);os.chown(path,user.pw_uid,user.pw_gid)
    # Persistent key/settings directory is not removed on mode switches or upgrades.
    nodes=[p for pattern in ('/dev/dri/*','/dev/snd/*','/dev/input/event*','/dev/video*','/dev/media*','/dev/dma_heap/*','/dev/mpp_service') for p in Path('/').glob(pattern.lstrip('/')) if p.is_char_device()]
    groups=sorted({user.pw_gid} | {p.stat().st_gid for p in nodes})
    os.environ.update(XDG_RUNTIME_DIR=str(runtime),WAYLAND_DISPLAY='wayland-g',
                      HOME='/state',XDG_CONFIG_HOME='/state/config',XDG_CACHE_HOME='/state/cache',
                      LIBSEAT_BACKEND='seatd',SEATD_SOCK='/run/seatd.sock',SEATD_VTBOUND='0',
                      QT_QPA_PLATFORM='wayland',SDL_VIDEODRIVER='wayland',LANG='C.UTF-8',
                      G_DEVICE_GROUPS=','.join(map(str,groups)))
    as_user=['setpriv','--reuid=kiosk','--regid=kiosk','--groups='+os.environ['G_DEVICE_GROUPS'],'--']
    audio=None
    radio_identity=None
    radio_owned=False
    try:
        if cfg['method']=='miracast':
            wifi_report(cfg['wifi_interface'])
            radio_identity=(Path('/sys/class/net')/cfg['wifi_interface']/'address').read_text()
        # Private system bus; never mount or control the router's D-Bus.
        Path('/run/dbus').mkdir(exist_ok=True)
        subprocess.run(['dbus-uuidgen','--ensure'],check=True)
        bus=launch(['dbus-daemon','--system','--nofork','--nopidfile'])
        wait_ready(lambda:Path('/run/dbus/system_bus_socket').is_socket(),bus,'D-Bus')
        os.environ['DBUS_SYSTEM_BUS_ADDRESS']='unix:path=/run/dbus/system_bus_socket'
        user_bus=launch(as_user+['dbus-daemon','--session','--nofork','--print-address=1'],stdout=subprocess.PIPE,text=True)
        if not select.select([user_bus.stdout],[],[],5)[0]:
            raise RuntimeError('Session bus timeout')
        address=user_bus.stdout.readline().strip()
        if not address or user_bus.poll() is not None:
            raise RuntimeError('Session bus failed')
        os.environ['DBUS_SESSION_BUS_ADDRESS']=address
        if cfg['method']=='airplay':
            avahi=launch(['avahi-daemon','--no-chroot','--no-drop-root'])
            time.sleep(.5)
            if avahi.poll() is not None: raise RuntimeError('Avahi failed; inspect mDNS ownership')
        outputs=[p.parent.name.removeprefix(cfg['drm_device']+'-') for p in Path('/sys/class/drm').glob(cfg['drm_device']+'-*/status') if p.read_text().strip()=='connected']
        display=module('g_display','/opt/profile-g/kiosk-wayland.py')
        text,selected=display.output_config(outputs,cfg['output'],cfg['rotation'])
        ini=runtime/'weston.ini';ini.write_text(text)
        seat=launch(['seatd','-u','kiosk','-g','kiosk'])
        wait_ready(lambda:Path('/run/seatd.sock').is_socket(),seat,'seatd')
        weston=launch(as_user+['/usr/bin/weston','--backend=drm','--drm-device='+cfg['drm_device'],
                     '--renderer=gl','--config='+str(ini),'--socket=wayland-g','--log=/state/weston.log'])
        wait_ready(lambda:(runtime/'wayland-g').is_socket(),weston,'Weston')
        audio_mod=module('g_audio','/opt/profile-g/hdmi-audio.py')
        # PulseAudio must run as the same user as the receiver.
        audio=audio_mod.AudioSession(lambda args,**kw:launch(as_user+args,**kw),children,cfg['drm_device'],selected)
        os.chown(runtime/'pulse',user.pw_uid,user.pw_gid)
        audio.start()
        if cfg['method']=='miracast':
            wifi=launch(['miracle-wifid','--use-dev','--interface',cfg['wifi_interface']])
            radio_owned=True
            index=(Path('/sys/class/net')/cfg['wifi_interface']/'ifindex').read_text().strip()
            def link_ready():
                return subprocess.run(['busctl','--system','introspect','org.freedesktop.miracle.wifi',
                       '/org/freedesktop/miracle/wifi/link/_'+format(ord(index[0]), '02x')+index[1:]],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
            wait_ready(link_ready,wifi,'MiracleCast link')
            receiver=launch(['miracle-sinkctl','--external-player','/opt/profile-g/miracle-player.py','run',index],stdin=subprocess.PIPE)
            link='/org/freedesktop/miracle/wifi/link/_'+format(ord(index[0]), '02x')+index[1:]
            bus_args=['busctl','--system']
            subprocess.run(bus_args+['set-property','org.freedesktop.miracle.wifi',link,
                           'org.freedesktop.miracle.wifi.Link','FriendlyName','s',cfg['name']],check=True,timeout=5)
            # The link exists before the asynchronous supplicant is ready for P2P.
            # Retry only during startup, never while a peer is streaming.
            for attempt in range(15):
                if stopping or wifi.poll() is not None or receiver.poll() is not None:
                    raise RuntimeError('Miracast stopped before discovery')
                subprocess.run(bus_args+['set-property','org.freedesktop.miracle.wifi',link,
                               'org.freedesktop.miracle.wifi.Link','P2PScanning','b','true'],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
                time.sleep(1)
                scan=subprocess.run(bus_args+['get-property','org.freedesktop.miracle.wifi',link,
                                    'org.freedesktop.miracle.wifi.Link','P2PScanning'],
                                    capture_output=True,text=True,timeout=5)
                if scan.returncode==0 and scan.stdout.strip()=='b true':
                    break
            else:
                raise RuntimeError('Miracast P2P discovery did not become ready')
        else:
            if cfg['method']=='steamlink':
                from steamlink import private_heap
                private_heap(user.pw_uid,user.pw_gid)
                xwayland=launch(as_user+['Xwayland',':9','-ac','-nolisten','tcp','-noreset','-fullscreen','-shm'])
                wait_ready(lambda:Path('/tmp/.X11-unix/X9').is_socket(),xwayland,'XWayland')
                os.environ['DISPLAY']=':9'
            receiver=launch(as_user+(['moonlight'] if cfg['mode']=='pair' and cfg['method']=='moonlight' else command(cfg)),
                            env=receiver_environment(cfg))
        print(json.dumps({'method':cfg['method'],'output':selected,'status':'started-not-stream-verified'}),flush=True)
        essential=[p for p in children if p is not audio.process]
        while not stopping:
            if any(p.poll() is not None for p in essential):
                raise RuntimeError('Receiver or supporting process exited; see container log')
            audio.tick();time.sleep(.25)
    finally:
        for child in reversed(children):
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            # Keep audio, XWayland and the compositor alive until their client exits.
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.wait()
        if radio_owned:
            address=Path('/sys/class/net')/cfg['wifi_interface']/'address'
            if address.exists() and address.read_text()==radio_identity:
                subprocess.run(['ip','link','set','dev',cfg['wifi_interface'],'down'],check=False)

if __name__=='__main__': main()
