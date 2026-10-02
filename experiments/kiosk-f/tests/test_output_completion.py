import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('completion', Path(__file__).resolve().parents[1] / 'cli/list-kiosk-outputs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OutputCompletion(unittest.TestCase):
    def test_only_actual_connected_x11_names(self):
        text = 'HDMI-1 connected primary 1080x1920+0+0 left (normal)\nHDMI-2 disconnected (normal)\nDP-3 connected 1920x1080+0+0\n'
        self.assertEqual(module.connected(text), ['DP-3', 'HDMI-1'])

    def test_target_and_no_shell(self):
        def run(args, **kwargs):
            self.assertEqual(args[-3:], ['screen-two', 'xrandr', '--query'])
            self.assertNotIn('shell', kwargs)
            self.assertEqual(kwargs['timeout'], 2)
            return SimpleNamespace(returncode=0, stdout='HDMI-1 connected primary 1x1+0+0\n')
        self.assertEqual(module.candidates('screen-two', run), ['auto', 'HDMI-1'])

    def test_bad_name_never_executes(self):
        def forbidden(*args, **kwargs):
            self.fail('must not execute')
        for name in ('', '--latest', '../other', 'screen;true', '$VAR(../../@)'):
            self.assertEqual(module.candidates(name, forbidden), ['auto'])

    def test_stopped_unavailable_and_timeout(self):
        self.assertEqual(module.candidates('screen', lambda *a, **kw: SimpleNamespace(returncode=125)), ['auto'])
        for error in (FileNotFoundError(), subprocess.TimeoutExpired('podman', 2)):
            def run(*args, **kwargs):
                raise error
            self.assertEqual(module.candidates('screen', run), ['auto'])


if __name__ == '__main__':
    unittest.main()
