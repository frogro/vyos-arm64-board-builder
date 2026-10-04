"""Keep uploaded UHD media and the pinned upstream policy boundary compatible."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch


class UploadResolution(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            'upload_policy', Path(__file__).resolve().parents[1] / 'adapter/i_profile.py')
        self.policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.policy)
        self.original = Mock(return_value='upstream policy')
        self.processing = types.SimpleNamespace(
            _HW_DECODE_VIDEO_CODECS={}, _pixel_cap_rejection=self.original)
        self.server = types.ModuleType('anthias_server')
        self.server.processing = self.processing
        self.modules = patch.dict(sys.modules, {'anthias_server': self.server})
        self.environment = patch.dict('os.environ')
        self.modules.start()
        self.environment.start()
        self.addCleanup(self.modules.stop)
        self.addCleanup(self.environment.stop)
        self.policy.configure()

    def check_resolution(self, width, height):
        return self.processing._pixel_cap_rejection(width, height, 'vyarm-browser-player')

    def test_full_hd_and_uhd_landscape_and_portrait_accepted(self):
        for dimensions in [(1920, 1080), (3840, 2160), (2160, 3840), (3840, 1600)]:
            with self.subTest(dimensions=dimensions):
                self.assertIsNone(self.check_resolution(*dimensions))
        self.original.assert_not_called()

    def test_above_uhd_rejected_including_low_pixel_count_wide_video(self):
        for dimensions in [(3841, 2160), (3840, 2161), (4096, 2160),
                           (7680, 4320), (4000, 1000), (2161, 3840)]:
            with self.subTest(dimensions=dimensions):
                self.assertIn('3840x2160', self.check_resolution(*dimensions))

    def test_other_device_retains_upstream_rules(self):
        result = self.processing._pixel_cap_rejection(3840, 2160, 'other-device')
        self.assertEqual(result, 'upstream policy')
        self.original.assert_called_once_with(3840, 2160, 'other-device')

    def test_repeated_configuration_does_not_wrap_itself(self):
        self.policy.configure()
        self.assertIsNone(self.check_resolution(3840, 2160))
        self.processing._pixel_cap_rejection(1920, 1080, 'other-device')
        self.original.assert_called_once_with(1920, 1080, 'other-device')


if __name__ == '__main__':
    unittest.main()
