import importlib.util
from pathlib import Path
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('restore',Path(__file__).resolve().parents[1]/'tools/audio/restore.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Restore(unittest.TestCase):
    def test_mixed_cards_first_start_and_existing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'card0').mkdir();(root/'card3').mkdir();(root/'ucm.conf').touch()
            state=root/'asound.state'
            with patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}), patch.object(m,'has_ucm',side_effect=[True,False]), patch.object(m.subprocess,'run') as run:
                m.restore(root,state)
                calls=[c.args[0] for c in run.call_args_list]
                self.assertNotIn('-U',calls[0]);self.assertIn('-U',calls[1])
                self.assertIn('init',calls[0]);self.assertEqual(calls[-1][-1],'store')
            state.touch()
            with patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}), patch.object(m,'has_ucm',return_value=False), patch.object(m.subprocess,'run') as run:
                m.restore(root,state)
                self.assertEqual(run.call_count,2)
                self.assertTrue(all('restore' in c.args[0] for c in run.call_args_list))
    def test_init_99_is_generic_but_restore_errors_propagate(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}):
            root=Path(tmp);(root/'card0').mkdir();(root/'ucm.conf').touch();state=root/'state'
            with patch.object(m,'has_ucm',return_value=False), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],99)):
                m.restore(root,state)  # store uses check=True in the real subprocess
                state.touch()
                with self.assertRaises(subprocess.CalledProcessError):m.restore(root,state)
            state.unlink()
            with patch.object(m,'has_ucm',return_value=False), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],5)):
                with self.assertRaises(subprocess.CalledProcessError):m.restore(root,state)

    def test_probe_only_enoent_allows_generic(self):
        for code, expected in [(0,True),(-2,False),(-22,None)]:
            with patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,str(code),'diagnostic')):
                if expected is None:
                    with self.assertRaises(RuntimeError):m.has_ucm('hw:0')
                else:self.assertEqual(m.has_ucm('hw:0'),expected)
    def test_missing_package_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}):
            root=Path(tmp);(root/'card0').mkdir()
            with self.assertRaisesRegex(RuntimeError,'Missing alsa-ucm-conf'):m.restore(root,root/'state')

if __name__=='__main__':unittest.main()
