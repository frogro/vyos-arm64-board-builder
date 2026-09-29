#!/usr/bin/env python3
"""Compare opt-in MPP VUI propagation without changing the installed plugin.
Usage: sudo python3 test-plugin-colorimetry.py CANDIDATE_PLUGIN NEW_OUTPUT_DIR
Recordings are synthetic; plugin selection and registry are private to this run.
"""
import json, os, subprocess, sys
from pathlib import Path

plugin=Path(sys.argv[1]).resolve(strict=True)
out=Path(sys.argv[2]); out.mkdir(mode=0o700)
plugins=out/'plugins'; plugins.mkdir()
# Avoid registry selection of the installed, differently versioned MPP plugin.
for p in Path('/usr/lib/aarch64-linux-gnu/gstreamer-1.0').glob('*.so'):
    if p.name!='libgstrockchipmpp.so': (plugins/p.name).symlink_to(p)
(plugins/'libgstrockchipmpp.so').symlink_to(plugin)
env=dict(os.environ, GST_PLUGIN_SYSTEM_PATH_1_0='', GST_PLUGIN_PATH_1_0=str(plugins),
         GST_REGISTRY_1_0=str(out/'registry.bin'))
inspection=subprocess.run(['gst-inspect-1.0','mpph264enc'],env=env,check=True,
                          capture_output=True,text=True,timeout=20)
(out/'plugin.txt').write_text(inspection.stdout)
assert str(plugins/'libgstrockchipmpp.so') in inspection.stdout, inspection.stdout
cases=[('bt709','tv','bt709','bt709','bt709'),
       ('bt601','tv','smpte170m','smpte170m','smpte170m'),
       ('1:3:5:1','pc','bt709','bt709','bt709')]
results=[]
for codec,encoder,parser in [('h264','mpph264enc','h264parse'),('hevc','mpph265enc','h265parse')]:
    for index,(color,rng,matrix,primaries,transfer) in enumerate(cases):
        for enabled in (False,True):
            label=f'{codec}-{index}-{int(enabled)}'; target=out/(label+'.'+codec)
            env['VYARM_MPP_COLORIMETRY']='1' if enabled else '0'
            cmd=['gst-launch-1.0','-q','videotestsrc','num-buffers=5','pattern=smpte','!',
                 f'video/x-raw,format=NV12,width=320,height=240,framerate=30/1,colorimetry={color}',
                 '!',encoder,'bps=1000000','gop=30','!',parser,'!','filesink',f'location={target}']
            run=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=20)
            (out/(label+'.log')).write_text(run.stdout+run.stderr)
            result={'codec':codec,'input_colorimetry':color,'enabled':enabled,'exit_code':run.returncode}
            if run.returncode==0:
                probe=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
                    '-show_entries','stream=codec_name,width,height,nb_read_frames,color_range,color_space,color_primaries,color_transfer',
                    '-of','json',str(target)],check=True,capture_output=True,text=True,timeout=15)
                stream=json.loads(probe.stdout)['streams'][0]; result['stream']=stream
                result['passed']=int(stream['nb_read_frames'])==5
                if enabled:
                    expected={'color_range':rng,'color_space':matrix,'color_primaries':primaries,'color_transfer':transfer}
                    result['expected']=expected
                    result['passed'] &= all(stream.get(k)==v for k,v in expected.items())
            else: result['passed']=False
            results.append(result)
            (out/'results.json').write_text(json.dumps({'tests':results},indent=2)+'\n')
report={'tests':results,'passed':all(t['passed'] for t in results)}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
raise SystemExit(0 if report['passed'] else 1)
