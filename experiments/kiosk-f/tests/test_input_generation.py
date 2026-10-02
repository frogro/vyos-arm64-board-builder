import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('kiosk', Path(__file__).resolve().parents[1] / 'cli/kiosk.py')
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)

class Inputs(unittest.TestCase):
    def config(self):
        return {'kiosk': {'url': 'file:///test'}, 'device': {
            'touch': {'source': '/dev/input/by-id/example-touch', 'destination': '/dev/input/event4'},
            'mouse': {'source': '/dev/input/by-id/example-mouse', 'destination': '/dev/input/event5'}}}

    def test_swapped_nodes_and_saved_config_unchanged(self):
        config = self.config()
        before = copy.deepcopy(config)
        result = kiosk.devices(config, lambda source: '/dev/input/event5' if source.endswith('touch') else '/dev/input/event4')
        self.assertEqual([d for _, d in result], ['/dev/input/event5', '/dev/input/event4'])
        self.assertEqual(config, before)

    def test_non_kiosk_unchanged(self):
        config = self.config()
        del config['kiosk']
        self.assertEqual([d for _, d in kiosk.devices(config, lambda _: self.fail('unexpected resolve'))],
                         ['/dev/input/event4', '/dev/input/event5'])

    def test_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            kiosk.devices(self.config(), lambda _: '/dev/input/event8')

    def test_missing_device_retained_as_metadata(self):
        def missing(_):
            raise FileNotFoundError('unplugged')
        self.assertEqual(kiosk.devices(self.config(), missing), [])
        self.assertTrue(any(x.startswith('# KioskInput=') for x in kiosk.environment(self.config())))

    def test_non_evdev_path_rejected(self):
        with self.assertRaisesRegex(ValueError, 'evdev'):
            kiosk.resolve_input('/dev/null')

    def test_only_stable_selected_kiosk_inputs_are_optional(self):
        item = self.config()['device']['touch']
        self.assertTrue(kiosk.optional_input(self.config(), item))
        self.assertFalse(kiosk.optional_input({}, item))
        self.assertFalse(kiosk.optional_input(self.config(), dict(item, source='/dev/input/event4')))
        self.assertFalse(kiosk.optional_input(self.config(), dict(item, destination='/dev/null')))

    def test_invalid_or_denied_input_still_rejected(self):
        def denied(_):
            raise PermissionError('denied')
        with self.assertRaisesRegex(ValueError, 'Cannot resolve'):
            kiosk.devices(self.config(), denied)

if __name__ == '__main__':
    unittest.main()
