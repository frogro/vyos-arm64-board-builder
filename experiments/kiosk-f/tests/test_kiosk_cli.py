import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('kiosk_cli', Path(__file__).resolve().parents[1] / 'cli/kiosk.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class KioskCLI(unittest.TestCase):
    def test_unrelated_containers_unchanged(self):
        self.assertEqual(module.environment({'environment': {'KIOSK_URL': {'value': 'old'}}}), [])

    def test_literal_url_and_systemd_percent(self):
        result = module.environment({'kiosk': {'url': 'https://example.org/menu?a=1&b=%20&c=$HOME', 'rotation': '90'}})
        self.assertEqual(result, ['Environment=KIOSK_URL="https://example.org/menu?a=1&b=%%20&c=$$HOME"',
                                 'Environment=KIOSK_OUTPUT="auto"', 'Environment=KIOSK_ROTATION="90"'])

    def test_graphics_is_explicit_and_validated(self):
        base = {'url': 'file:///opt/kiosk/input-test.html'}
        self.assertFalse(any('KIOSK_GRAPHICS' in line for line in module.environment({'kiosk': base})))
        for mode in ('software', 'auto'):
            result = module.environment({'kiosk': {**base, 'graphics': mode}})
            self.assertIn(f'Environment=KIOSK_GRAPHICS="{mode}"', result)
        with self.assertRaises(ValueError):
            module.environment({'kiosk': {**base, 'graphics': 'forced'}})

    def test_validation_before_generation(self):
        for setting in ({}, {'url': 'javascript:alert(1)'}, {'url': 'https://host/\nExecStart=bad'},
                        {'url': 'https://host/"bad'}, {'url': 'https://host/back\\slash'},
                        {'url': 'https://user:secret@host/'}, {'url': 'https://host:wrong/'},
                        {'url': 'file://remote/path'}, {'url': 'file:///a', 'rotation': '45'},
                        {'url': 'file:///a', 'output': '--auto'}, {'url': 'file:///a', 'unknown': 'x'}):
            with self.subTest(setting=setting), self.assertRaises(ValueError):
                module.environment({'kiosk': setting})

    def test_conflicting_old_environment_rejected(self):
        for variable in module.KEYS.values():
            with self.assertRaises(ValueError):
                module.environment({'kiosk': {'url': 'file:///a'}, 'environment': {variable: {'value': 'x'}}})

    def test_defaults_do_not_restrict_board_names(self):
        for output in ('HDMI-1', 'HDMI-A-2', 'DP-3', 'DSI-1', 'auto'):
            result = module.environment({'kiosk': {'url': 'file:///opt/kiosk/input-test.html', 'output': output}})
            self.assertIn(f'Environment=KIOSK_OUTPUT="{output}"', result)
            self.assertIn('Environment=KIOSK_ROTATION="0"', result)


if __name__ == '__main__':
    unittest.main()
