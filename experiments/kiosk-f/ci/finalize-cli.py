from pathlib import Path
import hashlib,json,subprocess,shutil
b=Path(__file__).resolve().parent
assert (b/'cli-status').read_text().strip()=='complete'
meta=json.loads((b/'cli-source/data/arm64-profile-source.json').read_text())
packages=list(b.glob('vyos-1x_*_arm64.deb'));assert len(packages)==1,packages
p=packages[0]
def cmd(*a):return subprocess.check_output(a,text=True).strip()
assert cmd('dpkg-deb','-f',str(p),'Version')==meta['package_version']
assert cmd('dpkg-deb','-f',str(p),'Architecture')=='arm64'
check=b/'cli-check';subprocess.run(['dpkg-deb','-x',str(p),str(check)],check=True)
control=b/'cli-control';subprocess.run(['dpkg-deb','-e',str(p),str(control)],check=True)
assert 'chmod u+s /usr/bin/vyos-op-run' in (control/'postinst').read_text()
for rel in ['usr/share/vyos/reftree.cache','usr/share/vyos/configd-include.json','usr/lib/python3/dist-packages/vyos/kiosk.py','usr/lib/python3/dist-packages/vyos/kiosk_remote.py','usr/libexec/vyos/conf_mode/container.py','usr/libexec/vyos/op_mode/kiosk_sunshine.py','usr/libexec/vyos/op_mode/kiosk_media.py','opt/vyatta/share/vyatta-cfg/templates/service/kvm-over-ip/video/colorimetry/node.def','opt/vyatta/share/vyatta-cfg/templates/container/name/node.tag/kiosk/display-backend/node.def','opt/vyatta/share/vyatta-cfg/templates/container/name/node.tag/kiosk/video-av1-buffers/node.def']:
 assert (check/rel).is_file(),rel
assert 'def decoder_devices(' in (check/'usr/lib/python3/dist-packages/vyos/kiosk.py').read_text()
assert 'optional_input' in (check/'usr/libexec/vyos/conf_mode/container.py').read_text()
r=check
op=r/'opt/vyatta/share/vyatta-op/templates'
show=(op/'show/log/console-server/node.def').read_text()
monitor=(op/'monitor/log/console-server/node.def').read_text()
assert 'conserver-server.service' in show and '--follow' not in show
assert 'conserver-server.service' in monitor and '--follow' in monitor
assert (op/'show/console-server/ports/node.def').is_file()
out=b/'cli-artifacts';out.mkdir(exist_ok=True)
shutil.copy2(p,out/p.name)
meta.update(package=p.name,package_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_commit='4e3e38a2e665bb2d8e9446116e02300bb38a2ab4',build_container_id=(b/'build-image-id.txt').read_text().strip(),build_host_arch='aarch64 native GitHub Actions',integration_commit='c0e39171807e14959611cfaa943e392f5d3b79db')
(out/'build.json').write_text(json.dumps(meta,indent=2)+'\n');(out/'SHA256SUMS').write_text(meta['package_sha256']+'  '+p.name+'\n')
print('CLI artifact and required D/F commands verified:',p.name)
