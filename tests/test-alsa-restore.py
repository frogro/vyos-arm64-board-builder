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
    def test_partial_state_initializes_only_missing_card(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}):
            root=Path(tmp);(root/'ucm.conf').touch()
            for i in (0,3):
                (root/f'card{i}').mkdir();(root/f'card{i}'/'id').write_text(f'HDMI{i}')
            state=root/'state';state.write_text('state.HDMI0 { control {} }\n')
            with patch.object(m,'has_ucm',side_effect=[True,False]), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
                m.restore(root,state)
                calls=[c.args[0] for c in run.call_args_list]
                self.assertIn('restore',calls[0]);self.assertNotIn('-U',calls[0])
                self.assertIn('init',calls[1]);self.assertIn('-U',calls[1])
                self.assertEqual(calls[2][-2:],['store','3'])
            with patch.object(m,'has_ucm',return_value=True), patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0)) as run:
                m.restore(root,state,selected='0');self.assertEqual(run.call_count,1)
    def test_state_parser_missing_quoted_and_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'state';self.assertFalse(m.saved_card(state,'hdmi0'))
            state.write_text('state."hdmi0" { control {} }')
            self.assertTrue(m.saved_card(state,'hdmi0'));self.assertFalse(m.saved_card(state,'hdmi1'))
            state.write_text('state.hdmi0 {')
            with self.assertRaises(RuntimeError):m.saved_card(state,'hdmi0')
    def test_probe_only_enoent_allows_generic(self):
        for code, expected in [(0,True),(-2,False),(-22,None)]:
            with patch.object(m.subprocess,'run',return_value=subprocess.CompletedProcess([],0,str(code),'diagnostic')):
                if expected is None:
                    with self.assertRaises(RuntimeError):m.has_ucm('hw:0')
                else:self.assertEqual(m.has_ucm('hw:0'),expected)
    def test_init99_allowed_but_other_errors_fail(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'ALSA_CONFIG_UCM2':tmp}):
            root=Path(tmp);(root/'ucm.conf').touch();(root/'card0').mkdir();(root/'card0/id').write_text('HDMI')
            for code in (99,5):
                with patch.object(m,'has_ucm',return_value=False), patch.object(m.subprocess,'run',side_effect=[subprocess.CompletedProcess([],code),subprocess.CompletedProcess([],0)]):
                    if code==99:m.restore(root,root/'state')
                    else:
                        with self.assertRaises(subprocess.CalledProcessError):m.restore(root,root/'state')

if __name__=='__main__':unittest.main()
