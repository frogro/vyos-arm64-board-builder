#!/usr/bin/env python3
"""Bounded synthetic check of D's actual GStreamer RGB -> NV12 negotiation.
Run with the explicitly loaded candidate module; does not load modules itself.
"""
import json, subprocess, tempfile
from pathlib import Path

results=[]
with tempfile.TemporaryDirectory(prefix='kvm-gst-colors-') as directory:
    out=Path(directory)/'frame.nv12'
    for fmt in ('BGR','RGB'):
        for space in ('bt601','bt709'):
            samples={}
            for converter in ('videoconvert','v4l2convert'):
                command=['gst-launch-1.0','-q','videotestsrc','num-buffers=1',
                         'pattern=solid-color','foreground-color=4294901760','!',
                         f'video/x-raw,format={fmt},width=1920,height=1080,colorimetry=sRGB',
                         '!',converter,'!',f'video/x-raw,format=NV12,colorimetry={space}',
                         '!','filesink',f'location={out}']
                run=subprocess.run(command,capture_output=True,text=True,timeout=12)
                if run.returncode:
                    samples[converter]={'error':run.stderr[-3000:]}
                else:
                    data=out.read_bytes()
                    if len(data)!=1920*1080*3//2: raise RuntimeError('Unexpected output size')
                    y=540*1920+960; uv=1920*1080+270*1920+960
                    samples[converter]=[data[y],data[uv],data[uv+1]]
            error=None
            if all(isinstance(v,list) for v in samples.values()):
                error=max(abs(a-b) for a,b in zip(samples['videoconvert'],samples['v4l2convert']))
            results.append(dict(format=fmt,colorspace=space,samples=samples,max_error=error))
report={'tests':results,'passed':all(t['max_error'] is not None and t['max_error']<=3 for t in results)}
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
