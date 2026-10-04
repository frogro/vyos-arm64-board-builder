#!/usr/bin/python3
import hashlib,importlib.util,json,tempfile,unittest,subprocess,itertools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
features=load('i_features','tools/feature-profile.py')
planner=load('i_plan','tools/ci/multimedia-plan.py')
stager=load('i_stage','experiments/profile-i/image/stage-runtime.py')
class SignageBuild(unittest.TestCase):
 def test_dependency_and_isolation(self):
  result=features.derive(False,False,False,signage_i=True)
  self.assertEqual(result['profile'],'kiosk-signage')
  self.assertEqual(result['enabled_features'],['kiosk-f','signage-i'])
  for board in ('rock-5b','orangepi5-plus'):
   result=planner.plan(board,signage=True)
   self.assertTrue(result['kiosk']);self.assertFalse(result['kvm']);self.assertFalse(result['receiver'])
  self.assertNotIn('signage_i',features.derive(True,False,False)['features'])
 def test_finalizer_profile_names_match_shared_planner(self):
  script=(ROOT/'tools/finalize-vyos-rootfs.sh').read_text()
  block=script[script.index('case "${EXTENDED_NETWORK}:'):script.index('ROOT="$(cd')]
  for network,tailscale,kvm,printing,receiver in itertools.product((False,True),repeat=5):
   result=features.derive(network,tailscale,kvm,kiosk_f=True,receiver_g=receiver,print_server_e=printing,signage_i=True)
   env=dict(EXTENDED_NETWORK='yes' if network else 'no',TAILSCALE_SUBNET_ROUTER='yes' if tailscale else 'no',KVM_OVER_IP='yes' if kvm else 'no',PRINT_SERVER_E='yes' if printing else 'no',KIOSK_F='yes',RECEIVER_G='yes' if receiver else 'no',SIGNAGE_I='yes',BUILD_PROFILE=result['profile'])
   completed=subprocess.run(['bash','-c',block],env=env,capture_output=True,text=True)
   self.assertEqual(completed.returncode,0,completed.stderr)
 def test_native_source_has_no_lab_paths_or_hotpatched_caches(self):
  prepare=load('i_source','experiments/profile-i/cli/prepare-source.py')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   prepare.prepare(root)
   for name in ('src/conf_mode/service_signage.py','src/helpers/vyarm-signage-supervisor.py'):
    self.assertTrue((root/name).is_file());self.assertNotIn('profile-i-lab',(root/name).read_text())
   self.assertFalse((root/'src/conf_mode/service_kvm_over_ip.py').exists())
 def test_verified_offline_stage(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'root';root.mkdir();a=Path(d)/'artifacts';a.mkdir()
   tags=['localhost/vyarm-signage:i-abc123','localhost/vyarm-signage-redis:22448b474134']
   info=[dict(Architecture='arm64',Id=str(n)*64,RepoTags=[tag],Config=dict(Labels={'io.vyarm.signage.version':'1'})) for n,tag in enumerate(tags)]
   blob=b'archive';(a/'runtime.tar').write_bytes(blob)
   meta=dict(profile='signage-i',tag=tags[0],redis_tag=tags[1],archive_sha256=hashlib.sha256(blob).hexdigest(),images=[dict(tag=tag,id=i['Id']) for tag,i in zip(tags,info)])
   (a/'runtime.json').write_text(json.dumps(meta));(a/'image.json').write_text(json.dumps(info))
   stager.stage(root,a)
   self.assertTrue((root/'usr/share/vyos-arm64-board-builder/signage-runtime/adapter/player.html').is_file())
   self.assertFalse((root/'config/profile-i').exists())
   self.assertFalse((root/'etc/systemd/system/multi-user.target.wants/vyarm-signage.service').exists())
   (a/'runtime.tar').write_bytes(b'corrupt')
   with self.assertRaisesRegex(ValueError,'checksum'):stager.stage(root,a)
if __name__=='__main__':unittest.main()
