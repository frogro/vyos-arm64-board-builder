#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fix', ROOT / 'tools/patch-hdmi-audio-dependency.py')
fix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fix)

class DependencyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'drivers/gpu/drm/display/drm_hdmi_audio_helper.c'
        self.source.parent.mkdir(parents=True)
        self.source.write_text('pdev = platform_device_register_data(dev, HDMI_CODEC_DRV_NAME, id, &data, sizeof(data));')
        self.config = self.source.parent / 'Kconfig'
        self.config.write_text('config DRM_DISPLAY_HDMI_AUDIO_HELPER\n\tbool\n\thelp\n\t  HDMI audio\n\nconfig OTHER\n\tbool\n')
        codec = self.root / 'sound/soc/codecs/Kconfig'
        codec.parent.mkdir(parents=True)
        codec.write_text('config SND_SOC_HDMI_CODEC\n\ttristate\n')

    def test_dependency_and_idempotence(self):
        fix.patch(self.root)
        first = self.config.read_text()
        self.assertIn('select SND_SOC_HDMI_CODEC if SND_SOC', first)
        self.assertTrue(first.endswith('config OTHER\n\tbool\n'))
        fix.patch(self.root)
        self.assertEqual(first, self.config.read_text())

    def test_kconfig_audio_states(self):
        try:
            import kconfiglib
        except ImportError:
            self.skipTest('kconfiglib not installed')
        fix.patch(self.root)
        fragment = self.config.read_text().split('config OTHER')[0]
        fragment = fragment.replace('\tbool\n', '\tbool "Helper"\n')
        top = self.root / 'Kconfig'
        top.write_text('config MODULES\n\tbool\n\toption modules\n\tdefault y\n'
                       'config SND_SOC\n\ttristate "Audio"\n' + fragment +
                       'config SND_SOC_HDMI_CODEC\n\ttristate\n')
        for helper, audio, expected in [('y', 'y', 'y'), ('y', 'm', 'm'),
                                        ('y', 'n', 'n'), ('n', 'y', 'n')]:
            with self.subTest(helper=helper, audio=audio):
                k = kconfiglib.Kconfig(str(top), warn=False)
                k.syms['SND_SOC'].set_value(audio)
                k.syms['DRM_DISPLAY_HDMI_AUDIO_HELPER'].set_value(helper)
                self.assertEqual(k.syms['SND_SOC_HDMI_CODEC'].str_value, expected)

    def test_no_helper_unchanged(self):
        self.source.unlink()
        before = self.config.read_text()
        fix.patch(self.root)
        self.assertEqual(before, self.config.read_text())

    def test_other_implementation_unchanged(self):
        self.source.write_text('/* no codec registration */')
        before = self.config.read_text()
        fix.patch(self.root)
        self.assertEqual(before, self.config.read_text())

    def test_unexpected_kconfig_fails(self):
        self.config.write_text('config OTHER\n\tbool\n')
        with self.assertRaises(ValueError):
            fix.patch(self.root)

if __name__ == '__main__':
    unittest.main()
