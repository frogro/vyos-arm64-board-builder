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
            session=audio.PulseSession(launch, children)
            session.tick();first=session.process
            session.tick();self.assertEqual(children,[first])
            first.poll.return_value=1
            session.retry=0;session.tick()
            self.assertEqual(children,[session.process]);self.assertIsNot(first,session.process)
            self.assertEqual(os.environ['PULSE_SERVER'],'unix:'+tmp+'/pulse/native')
    def test_missing_audio_binary_is_nonfatal(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil, 'which', return_value=None):
            launch=Mock();session=audio.PulseSession(launch,[]);session.start();launch.assert_not_called()
    def test_probe_timeout_does_not_kill_display_start(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil,'which',return_value='/bin/test'), patch.object(audio.subprocess,'run',side_effect=subprocess.TimeoutExpired('pactl',2)):
            proc=Mock();proc.poll.return_value=None
            session=audio.PulseSession(Mock(return_value=proc),[]);session.start()


class DisplayAudioTests(unittest.TestCase):
    def test_selected_x11_output_and_ambiguous_auto(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp, 'KIOSK_OUTPUT':'HDMI-2'}):
            root=Path(tmp)/'drm'
            for name in ('card3-HDMI-A-1', 'card3-HDMI-A-2'):
                connector=root/name;connector.mkdir(parents=True)
                (connector/'status').write_text('connected')
            self.assertEqual(audio.kiosk_connector(root),('card3','HDMI-A-2'))
            with patch.dict(os.environ, {'KIOSK_OUTPUT':'auto'}):
                self.assertEqual(audio.kiosk_connector(root),(None,None))
            (Path(tmp)/'display.json').write_text('{"output":"HDMI-A-1"}')
            self.assertEqual(audio.kiosk_connector(root),('card3','HDMI-A-1'))

    def test_private_server_hotplug_and_no_unused_card_probe(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_RUNTIME_DIR':tmp}), patch.object(audio.shutil,'which',return_value='/bin/test'):
            proc=Mock();proc.poll.return_value=None
            launch=Mock(return_value=proc)
            session=audio.AudioSession(launch,[], 'card3','HDMI-A-1')
            session.pactl=Mock(return_value=subprocess.CompletedProcess([],0,'7\n',''))
            with patch.object(audio,'select_device',return_value='plughw:9,0'):
                session.tick()
            self.assertIn('-n',launch.call_args.args[0])
            self.assertNotIn('udev', (Path(tmp)/'hdmi-pulse.pa').read_text())
            self.assertEqual(session.device,'plughw:9,0')
            with patch.object(audio,'select_device',return_value=None):
                session.next_check=0;session.tick()
            session.pactl.assert_any_call('unload-module','7')
            session.pactl.assert_any_call('set-default-sink','vyarm_silent')
            self.assertIsNone(session.device)

if __name__=='__main__':unittest.main()
