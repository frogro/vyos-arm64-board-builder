from pathlib import Path
import json,runpy,subprocess
root=Path(__file__).resolve().parents[1]
ssh=runpy.run_path('/tmp/av1-remote.py')['SSH']
remote='/config/kiosk-test/av1-timeout-cli-20260922'
def upload(name,data):
 subprocess.run(ssh+['sudo tee '+remote+'/'+name+' >/dev/null'],input=data,text=True,check=True)
manifest={'version':1,'binary':'/candidate-p010/chrome','sha256':'d1f979a39d0402060364e5a9202cb6e8772a7e3ec90c91622151defcb851eeb6','backend':'v4l2-request','graphics_backend':'wayland','arguments':[], 'base_features':['AcceleratedVideoDecoder','AcceleratedVideoDecodeLinuxGL','PreferV4L2VideoAcceleration'], 'features':['V4L2ExtraCaptureBuffers','V4L2ExtraAV1CaptureBuffers']}
(root/'av1-timeout-cli-20260922/media-capabilities.json').write_text(json.dumps(manifest,indent=2)+'\n')
upload('media-capabilities.json',json.dumps(manifest));upload('kiosk-media.py',(root/'container/kiosk-media.py').read_text())
s=(root/'chromium-nuc-live-20260922/probe-color.py').read_text()
marker="p=subprocess.Popen(['bash','-c'"
idx=s.index(marker)
s=s[:idx]+'''import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('media_policy','/kiosk-media.py')
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
policy.MANIFEST=Path('/media-capabilities.json');policy.STATUS=Path('/tmp/media-policy.json')
policy_args,policy_status=policy.browser_policy(os.environ)
flags=[f for f in flags if not f.startswith(('--enable-features=','--disable-accelerated-video-decode'))]
flags+=policy_args
if policy_status['active_features']:
 flags+=['--enable-features='+','.join(policy_status['active_features'])]
'''+s[idx:]
s=s.replace("{'webrtc':webrtc,", "{'mediaPolicy':policy_status,'webrtc':webrtc,")
upload('probe-cli.py',s);(root/'av1-timeout-cli-20260922/probe-cli.py').write_text(s)
s=(root/'chromium-nuc-live-20260922/run-p010.sh').read_text()
s=s.replace(' -e ACCURATE_YUV_MATRIX=', ' -e KIOSK_VIDEO_DECODE="${KIOSK_VIDEO_DECODE:-auto}" -e KIOSK_VIDEO_AV1_BUFFERS="${KIOSK_VIDEO_AV1_BUFFERS:-disabled}" -v '+remote+'/kiosk-media.py:/kiosk-media.py:ro -v '+remote+'/media-capabilities.json:/media-capabilities.json:ro \\\n -e ACCURATE_YUV_MATRIX=')
s=s.replace('$root/probe-color.py:/probe.py:ro',remote+'/probe-cli.py:/probe.py:ro')
upload('run-cli-browser.sh',s);(root/'av1-timeout-cli-20260922/run-cli-browser.sh').write_text(s)
s=(root/'av1-reset-research-20260922/av1-pulse-browser-noevents.sh').read_text()
s=s.replace('av1-reset-research-20260922/pulse-browser-no-events','av1-timeout-cli-20260922/browser-cli')
s=s.replace('vyarm-av1-pulse','vyarm-av1-cli').replace('av1-reset-research-20260922/hantro-pulse.ko','av1-timeout-cli-20260922/hantro-timeout.ko')
start=s.index('PROBE_BROWSER=');end=s.index('echo DECODE_DONE',start)
s=s[:start]+'''for mode in auto software; do
 reserve=disabled
 [[ $mode != auto ]] || reserve=enabled
 KIOSK_VIDEO_DECODE=$mode KIOSK_VIDEO_AV1_BUFFERS=$reserve PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash /config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh av1 "$root/av1-main10-fixtures" "media-cli-$mode" 0 "$video" "$media"
done
KIOSK_VIDEO_DECODE=auto KIOSK_VIDEO_AV1_BUFFERS=enabled PROBE_BROWSER=/candidate-p010/chrome PROBE_TIMEOUT=45 bash /config/kiosk-test/av1-timeout-cli-20260922/run-cli-browser.sh av1 "$root/av1-main10-fixtures" media-cli-no-decoder 0
'''+s[end:]
upload('run-cli-suite.sh',s);(root/'av1-timeout-cli-20260922/run-cli-suite.sh').write_text(s)
