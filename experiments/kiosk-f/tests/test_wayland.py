import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('wayland', Path(__file__).parents[1] / 'container/kiosk-wayland.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class WaylandTests(unittest.TestCase):
    def test_rotation_matches_counterclockwise_cli_and_disables_other_output(self):
        config, selected = w.output_config(['HDMI-A-1', 'HDMI-A-2'], 'HDMI-1', '90')
        self.assertEqual(selected, 'HDMI-A-1')
        self.assertIn('transform=rotate-270', config)
        self.assertIn('name=HDMI-A-2\nmode=off', config)

    def test_ambiguous_auto_and_missing_output_rejected(self):
        for outputs, requested in [([], 'auto'), (['HDMI-A-1', 'HDMI-A-2'], 'auto'), (['HDMI-A-1'], 'HDMI-2')]:
            with self.assertRaises(ValueError): w.output_config(outputs, requested, '0')

    def test_unrecognised_rotation_rejected(self):
        with self.assertRaises(ValueError): w.output_config(['HDMI-A-1'], 'auto', '45')
