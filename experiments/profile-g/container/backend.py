#!/usr/bin/env python3
"""Receiver commands; command vectors only, no shell interpolation."""
import base64
import json
import os
import shutil
import subprocess
import sys
sys.path.insert(0, '/opt/profile-g')
from receiver import settings

def config():
    return settings(json.loads(base64.b64decode(os.environ['G_RECEIVER_CONFIG'], validate=True)))

def gst_decoder(policy, available=None):
    available = available or (lambda name: subprocess.run(['gst-inspect-1.0',name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
    if policy == 'software':
        return 'avdec_h264'
    if policy == 'auto':
        return 'decodebin'
    for name in ('v4l2slh264dec','mppvideodec','v4l2h264dec'):
        if available(name):
            return name
    raise ValueError('No H264 hardware GStreamer decoder found; use auto/software or install a compatible media runtime')

def receiver_environment(cfg, inherited=None):
    """Keep the tested H.264 library private to Moonlight, including its CPU fallback."""
    env = dict(os.environ if inherited is None else inherited)
    if (cfg['method'] == 'moonlight' and cfg['mode'] == 'receive'
            and cfg['codec'] == 'h264' and cfg['decoder'] != 'software'):
        env['LD_LIBRARY_PATH'] = '/opt/ffmpeg-request/lib'
        env['DRM_FORCE_EGL'] = '1'
    return env

def command(cfg):
    if cfg['method'] == 'airplay':
        return ['uxplay','-n',cfg['name'],'-s',cfg['resolution'],'-fps',cfg['fps'],
                '-pin','-reg','/state/airplay-clients','-key','/state/airplay-key',
                '-vd',gst_decoder(cfg['decoder']),'-vs','waylandsink fullscreen=true',
                '-as','pulsesink']
    if cfg['method'] == 'moonlight':
        return ['moonlight','stream',cfg['host'],cfg['app'],'--resolution',cfg['resolution'],
                '--fps',cfg['fps'],'--bitrate',cfg['bitrate'],'--display-mode','borderless',
                '--video-decoder',cfg['decoder'],'--video-codec',
                {'auto':'auto','h264':'H.264','hevc':'HEVC','av1':'AV1'}[cfg['codec']],
                '--capture-system-keys','never']
    raise ValueError('Miracast uses its separate privileged network controller')

if __name__ == '__main__':
    cfg=config()
    args=['moonlight'] if len(sys.argv)>1 and sys.argv[1]=='pair' else command(cfg)
    if not shutil.which(args[0]):
        raise SystemExit('Receiver binary missing: '+args[0])
    os.execvpe(args[0],args,receiver_environment(cfg))
