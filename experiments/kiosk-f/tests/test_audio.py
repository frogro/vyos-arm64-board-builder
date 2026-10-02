import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('audio', Path(__file__).parents[1]/'container/kiosk-audio.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)

class AudioTests(unittest.TestCase):
    def test_reuses_live_server_and_reaps_dead_child_before_retry(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil, 'which', return_value='/bin/test'):
            children=[]
            def launch(args):
                proc=Mock();proc.poll.return_value=None;children.append(proc);return proc
            session=audio.AudioSession(launch, children)
            session.tick();first=session.process
            session.tick();self.assertEqual(children,[first])
            first.poll.return_value=1
            session.retry=0;session.tick()
            self.assertEqual(children,[session.process]);self.assertIsNot(first,session.process)
            self.assertEqual(os.environ['PULSE_SERVER'],'unix:'+tmp+'/pulse/native')
    def test_missing_audio_binary_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil, 'which', return_value=None):
            launch=Mock();session=audio.AudioSession(launch,[]);session.start();launch.assert_not_called()
    def test_probe_timeout_does_not_kill_display_start(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil,'which',return_value='/bin/test'), patch.object(audio.subprocess,'run',side_effect=subprocess.TimeoutExpired('pactl',2)):
            proc=Mock();proc.poll.return_value=None
            session=audio.AudioSession(Mock(return_value=proc),[]);session.start()

if __name__=='__main__':unittest.main()
