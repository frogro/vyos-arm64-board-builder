import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
CHECKER = ROOT / 'experiments/kiosk-f/ci/check-main-preservation.py'

class MainPolicy(unittest.TestCase):
    def test_exact_delta_passes_but_additional_changes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def write(path, text):
                p=root/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
            def git(*args):
                subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid',*args],cwd=root,check=True,capture_output=True)
            git('init','-q')
            write('tools/feature-profile.py','def derive(*args): return args\n')
            write('tools/ci/board-build-packages.txt','gcc\n')
            write('.github/workflows/build-board-candidate.yml','tools/ci/board-build-packages.txt\n')
            write('profiles/hardware.config','old\n')
            git('add','.'); git('commit','-qm','baseline'); git('tag','baseline')
            write('profiles/hardware.config','reviewed\n')
            git('add','.'); git('commit','-qm','candidate')
            digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
            entry={'base_sha256':digest('old\n'),'candidate_sha256':digest('reviewed\n')}
            write('experiments/profile-g/ci/reviewed-hardware-delta.json',json.dumps({'schema':1,'files':{'profiles/hardware.config':entry}}))
            def check():return subprocess.run(['python3',str(CHECKER),'baseline'],cwd=root,capture_output=True,text=True)
            self.assertEqual(check().returncode,0)
            write('profiles/hardware.config','unreviewed\n')
            result=check(); self.assertNotEqual(result.returncode,0); self.assertIn('drifted',result.stderr)
            write('profiles/hardware.config','reviewed\n')
            write('profiles/unreviewed.config','other\n');git('add','profiles');git('commit','-qm','unknown change')
            result=check();self.assertNotEqual(result.returncode,0);self.assertIn('profiles/unreviewed.config',result.stderr)

if __name__=='__main__':unittest.main()
