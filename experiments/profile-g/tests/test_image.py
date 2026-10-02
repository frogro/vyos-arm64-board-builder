import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,ROOT/rel)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
stage=load('g_stage','experiments/profile-g/image/stage-runtime.py')
imp=load('g_import','experiments/profile-g/image/import-runtime.py')
ci=load('g_ci','experiments/profile-g/ci/prepare-ci.py')

class OfflineG(unittest.TestCase):
    def fixture(self,base):
        root=base/'root';root.mkdir();art=base/'art';art.mkdir()
        archive=b'isolated receiver archive';(art/'runtime.tar').write_bytes(archive)
        meta=dict(profile='receiver-g',tag='localhost/vyarm-receiver:g-123abc',archive_sha256=hashlib.sha256(archive).hexdigest())
        (art/'runtime.json').write_text(json.dumps(meta))
        info=dict(Architecture='arm64',Id='sha256:'+'a'*64,RepoTags=[meta['tag']],Config={'Labels':{'io.vyarm.receiver.version':'1'}})
        (art/'image.json').write_text(json.dumps([info]))
        return root,art
    def test_preserves_existing_state_and_kiosk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,art=self.fixture(Path(tmp))
            for rel in ['config/config.boot','config/tailscale/tailscaled.state','config/kiosk/sunshine_state.json','usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.tar']:
                p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('existing')
            stage.stage(root,art)
            for rel in ['config/config.boot','config/tailscale/tailscaled.state','config/kiosk/sunshine_state.json','usr/share/vyos-arm64-board-builder/kiosk-runtime/runtime.tar']:
                self.assertEqual((root/rel).read_text(),'existing')
            self.assertFalse((root/'etc/systemd/system/vyos-container-receiver.service').exists())
            self.assertTrue((root/'etc/systemd/system/vyos.target.wants/vyarm-receiver-runtime.service').is_symlink())
            staged=root/'usr/share/vyos-arm64-board-builder/receiver-runtime'
            calls=[]
            def run(args,**kw):
                calls.append(args)
                if args[1:3]==['image','exists']:return SimpleNamespace(returncode=1)
                return SimpleNamespace(returncode=0,stdout='sha256:'+'a'*64)
            imp.install(staged,run)
            self.assertTrue(any(a[1]=='load' for a in calls))
            self.assertFalse(any(a[1] in ['run','start','rm'] for a in calls))
    def test_rejects_corrupt_archive_before_staging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,art=self.fixture(Path(tmp));(art/'runtime.tar').write_bytes(b'wrong')
            with self.assertRaises(ValueError):stage.stage(root,art)
            self.assertEqual(list(root.iterdir()),[])
    def test_does_not_replace_existing_versioned_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,art=self.fixture(Path(tmp));stage.stage(root,art);calls=[]
            def run(args,**kw):
                calls.append(args);return SimpleNamespace(returncode=0,stdout='sha256:'+'b'*64)
            with self.assertRaises(ValueError):imp.install(root/'usr/share/vyos-arm64-board-builder/receiver-runtime',run)
            self.assertFalse(any(a[1]=='load' for a in calls))
    def test_full_image_adapter_keeps_baseline_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);ci.prepare(out)
            for p in out.glob('*.sh'):subprocess.run(['bash','-n',str(p)],check=True)
            for p in out.glob('*.py'):compile(p.read_text(),str(p),'exec')
            verify=(out/'verify-full.sh').read_text()
            for term in ['receiver-runtime/runtime.tar','kiosk-runtime/runtime.tar','vyos-kvm-cached-launch','lsinitramfs','ssh_host_*_key','receiver_g','network-tailscale-kvm-kiosk-receiver']:
                self.assertIn(term,verify)
            self.assertIn('--kvm --tailscale --kiosk --receiver',(out/'build-cli.sh').read_text())
