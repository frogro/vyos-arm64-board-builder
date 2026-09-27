from pathlib import Path
import json,hashlib,datetime,os
w=Path('/work')
m={'schema':1,'built_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'board':'rock-5b','profile':'network-tailscale-kvm-kiosk','experimental':True,'integration_source':'c0e39171807e14959611cfaa943e392f5d3b79db','workflow_commit':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],'base_ad_run':'36267716867','base_vyos':'999.202609250800','cli':json.loads((w/'cli-artifacts/build.json').read_text()),'runtime':json.loads((w/'runtime-artifacts/runtime.json').read_text()),'kernel_hashes':(w/'kernel-artifacts/SHA256SUMS').read_text(),'verification':(w/'verification-complete').read_text().strip(),'input_archive_hashes':(w/'inputs.sha256').read_text(),'native_tools':json.loads((w/'native-pack/SHA256.json').read_text()),'files':{}}
for p in (w/'output').iterdir():
    if p.name.endswith(('.img.xz','.iso')):
        with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        m['files'][p.name]={'bytes':p.stat().st_size,'sha256':h}
(w/'output/build-provenance.json').write_text(json.dumps(m,indent=2)+'\n')
