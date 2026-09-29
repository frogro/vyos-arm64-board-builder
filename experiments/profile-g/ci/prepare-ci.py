#!/usr/bin/env python3
"""Extend the established A-D/F CI scripts; fail if reviewed anchors change."""
from pathlib import Path
import shutil,sys
ROOT=Path(__file__).resolve().parents[3]

def prepare(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'experiments/kiosk-f/ci').iterdir():
        if p.is_file():shutil.copyfile(p,out/p.name)
    def change(file,old,new,count=1):
        p=out/file;s=p.read_text()
        if s.count(old)!=count:raise ValueError(f'Changed CI anchor: {file}: {old}')
        p.write_text(s.replace(old,new))
    profile='network-tailscale-kvm-kiosk'
    for name in ['prepare-full.sh','assemble.sh','verify-full.sh','manifest.py']:
        p=out/name;p.write_text(p.read_text().replace(profile,profile+'-receiver'))
    change('prepare-full.sh','KIOSK_F=yes\n','KIOSK_F=yes\nRECEIVER_G=yes\n')
    change('prepare-full.sh','truncate -s 12G','truncate -s 16G')
    change('assemble.sh','export KIOSK_F=yes','export RECEIVER_G=yes RECEIVER_G_RUNTIME=/work/receiver-artifacts\nexport KIOSK_F=yes')
    change('build-cli.sh','--tailscale --kiosk','--tailscale --kiosk --receiver')
    shutil.copyfile(ROOT/'experiments/profile-g/ci/cli-recipe.sha256',out/'cli-recipe.sha256')
    change('finalize-cli.py',"for rel in [", "for rel in ['usr/lib/python3/dist-packages/vyos/receiver.py','usr/libexec/vyos/op_mode/receiver.py','opt/vyatta/share/vyatta-cfg/templates/container/name/node.tag/receiver/method/node.def',")
    change('verify-full.sh',"assert m['features']['kiosk_f']", "assert m['features']['receiver_g'];assert m['features']['kiosk_f']")
    change('verify-full.sh',"assert 'optional_input' in", """assert json.loads((r/'usr/share/vyos-arm64-board-builder/receiver-runtime/runtime.json').read_text())['profile']=='receiver-g'
import runpy
update_patch=runpy.run_path('/work/repo/tools/patch-vyos-system-image-dtb.py')
installer=(r/'usr/libexec/vyos/op_mode/image_installer.py').read_text()
assert update_patch['METADATA_HELPER'].strip() in installer, 'Configuration metadata helper missing from SD/ISO rootfs'
assert update_patch['CONFIG_COPY_ANCHOR'] + update_patch['METADATA_CALL'] in installer, 'Configuration metadata migration not called'
assert not (r/'etc/systemd/system/vyos-container-receiver.service').exists()
assert (r/'etc/systemd/system/vyos.target.wants/vyarm-receiver-runtime.service').is_symlink()
assert 'optional_input' in""")
    change('verify-full.sh',"assert owner(['container','name','kiosk','kiosk','display-backend']", "assert owner(['container','name','test','receiver','method'],with_tag=True)=='container'\nassert owner(['container','name','kiosk','kiosk','display-backend']")
    change('verify-full.sh','cmp runtime-artifacts/runtime.tar',"cmp receiver-artifacts/runtime.tar \"$V/root/usr/share/vyos-arm64-board-builder/receiver-runtime/runtime.tar\"\ncmp repo/experiments/profile-g/cli/receiver.py \"$V/root/usr/lib/python3/dist-packages/vyos/receiver.py\"\ncmp runtime-artifacts/runtime.tar")
    change('manifest.py',"'runtime':json.loads", "'receiver_source_run':(w/'receiver-artifacts/source-run.txt').read_text().strip(),'receiver_runtime':json.loads((w/'receiver-artifacts/runtime.json').read_text()),'runtime':json.loads")

if __name__=='__main__':prepare(sys.argv[1])
