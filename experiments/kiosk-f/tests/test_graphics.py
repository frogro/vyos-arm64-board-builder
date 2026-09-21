import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('graphics', Path(__file__).parents[1] / 'container/kiosk-graphics.py')
GRAPHICS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GRAPHICS)


class GraphicsTests(unittest.TestCase):
    template = 'Section "Device"\n Option "AccelMethod" "none"\nEndSection\n'

    def test_default_software_preserves_template_with_gpu(self):
        self.assertEqual(GRAPHICS.prepare('software', self.template, ['renderD129']), (self.template, False))

    def test_auto_without_granted_gpu_preserves_software(self):
        self.assertEqual(GRAPHICS.prepare('auto', self.template, []), (self.template, False))

    def test_auto_uses_available_node_without_fixed_number_or_board(self):
        text, active = GRAPHICS.prepare('auto', self.template, ['renderD130'])
        self.assertTrue(active)
        self.assertIn('"glamor"', text)

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            GRAPHICS.prepare('fast', self.template, [])

    def test_unexpected_template_rejected(self):
        for template in ('', self.template * 2):
            with self.assertRaises(ValueError):
                GRAPHICS.prepare('auto', template, ['renderD128'])
