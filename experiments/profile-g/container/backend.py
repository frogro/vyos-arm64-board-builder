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

def gst_selection(resolution):
    try:
        return json.loads(subprocess.check_output([sys.executable, '/opt/profile-g/media.py', 'select', resolution], text=True, timeout=10))
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'selected': None, 'ranks': {}, 'probe_error': 'V4L2 capability probe unavailable'}

def gst_decoder(policy, available=None, resolution='1920x1080'):
    if policy == 'software':
        return 'avdec_h264'
    if policy == 'auto':
        return 'decodebin'
    if available is None:
        selected = gst_selection(resolution)['selected']
        if selected:
            return selected
        names = ('mppvideodec','v4l2h264dec')
        available = lambda name: subprocess.run(['gst-inspect-1.0',name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    else:
        names = ('v4l2slh264dec','mppvideodec','v4l2h264dec')
    for name in names:
        if available(name):
            return name
    raise ValueError('No suitable H264 hardware decoder for '+resolution+'; inspect receiver media diagnostics')

def gst_environment(cfg, env):
    if cfg['decoder'] == 'software':
        return env
    selected = gst_selection(cfg['resolution'])
    ranks = selected.get('ranks', {})
    if ranks:
        existing = [item for item in env.get('GST_PLUGIN_FEATURE_RANK','').split(',') if item and item.split(':')[0] not in ranks]
        env['GST_PLUGIN_FEATURE_RANK'] = ','.join(existing+[f'{name}:{rank}' for name,rank in ranks.items()])
    return env

def receiver_environment(cfg, inherited=None):
    """Keep Request libraries private to supported Moonlight codecs. Auto uses H264 until broader negotiation is qualified."""
    env = dict(os.environ if inherited is None else inherited)
    # Moonlight probes decoder capabilities when opening its GUI before streaming.
    # Pair mode must see the same Request libraries as the qualified H.264 stream.
    if (cfg['method'] == 'moonlight' and cfg['decoder'] != 'software'
            and (cfg['mode'] == 'pair' or cfg['codec'] in ('auto','h264','hevc'))):
        env['LD_LIBRARY_PATH'] = '/opt/ffmpeg-request/lib'
        env['DRM_FORCE_EGL'] = '1'
    if cfg['method'] in ('airplay','miracast'):
        env = gst_environment(cfg, env)
    return env

def command(cfg):
    if cfg['method'] == 'airplay':
        return ['uxplay','-n',cfg['name'],'-s',cfg['resolution'],'-fps',cfg['fps'],
                '-pin','-reg','/state/airplay-clients','-key','/state/airplay-key',
                '-vd',gst_decoder(cfg['decoder'], resolution=cfg['resolution']),'-vs','waylandsink fullscreen=true',
                '-as','pulsesink']
    if cfg['method'] == 'moonlight':
        return ['moonlight','stream',cfg['host'],cfg['app'],'--resolution',cfg['resolution'],
                '--fps',cfg['fps'],'--bitrate',cfg['bitrate'],'--display-mode','borderless',
                '--video-decoder',cfg['decoder'],'--video-codec',
                {'auto':('H.264' if cfg['decoder'] != 'software' else 'auto'),'h264':'H.264','hevc':'HEVC','av1':'AV1'}[cfg['codec']],
                '--capture-system-keys','never']
    if cfg['method'] == 'steamlink':
        return ['python3','/opt/profile-g/steamlink.py']
    raise ValueError('Miracast uses its separate privileged network controller')

if __name__ == '__main__':
    cfg=config()
    args=['moonlight'] if len(sys.argv)>1 and sys.argv[1]=='pair' else command(cfg)
    if not shutil.which(args[0]):
        raise SystemExit('Receiver binary missing: '+args[0])
    os.execvpe(args[0],args,receiver_environment(cfg))
