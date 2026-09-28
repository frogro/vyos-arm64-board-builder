#!/usr/bin/env python3
"""MiracleCast external player: bounded queues, unprivileged Wayland output."""
import argparse
import os
import sys
sys.path.insert(0,'/opt/profile-g')
from backend import config, gst_decoder

def pipeline(port, audio, cfg):
    # RTP jitter is already bounded by cfg['latency']; avoid tsdemux's extra 700 ms.
    # An advertised but absent audio track must not hold video in preroll.
    args=['gst-launch-1.0','-e','udpsrc',f'port={port}',
          'caps=application/x-rtp,media=video,clock-rate=90000,encoding-name=MP2T,payload=33',
          '!','rtpjitterbuffer','latency='+cfg['latency'],'drop-on-latency=true',
          '!','rtpmp2tdepay','!','tsdemux','latency=0','name=demux','demux.',
          '!','video/x-h264','!','queue','max-size-buffers=4','max-size-bytes=0','max-size-time=100000000',
          '!','h264parse','!',gst_decoder(cfg['decoder']),'!','videoconvert',
          '!','waylandsink','fullscreen=true']
    if audio:
        args += ['demux.','!','audio/mpeg','!','queue','max-size-buffers=0','max-size-bytes=0','max-size-time=100000000',
                 '!','aacparse','!','avdec_aac','!','audioconvert','!','audioresample','!','pulsesink','async=false','buffer-time=40000','latency-time=10000']
    return args

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('-p',type=int,required=True)
    p.add_argument('-a',action='store_true');p.add_argument('-r');p.add_argument('-s');p.add_argument('-d')
    a=p.parse_args()
    if not 1024 <= a.p <= 65535: p.error('Invalid RTP port')
    args=pipeline(a.p,a.a,config())
    if os.getuid()==0:
        args=['setpriv','--reuid=kiosk','--regid=kiosk','--groups='+os.environ['G_DEVICE_GROUPS'],'--']+args
    os.execvp(args[0],args)
