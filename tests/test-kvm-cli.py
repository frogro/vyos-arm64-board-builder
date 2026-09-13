#!/usr/bin/env python3

from pathlib import Path
import py_compile
import subprocess
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class KvmCliTests(unittest.TestCase):
    def test_cli_backend_names_are_generic(self):
        xml_path = ROOT / 'profiles/kvm-cli/service_kvm-over-ip.xml'
        tree = ET.parse(xml_path)
        text = xml_path.read_text()

        self.assertIn('ustreamer gstreamer ffmpeg', text)
        self.assertNotIn('backend ffmpeg-rockchip', text)
        self.assertNotIn('backend gstreamer-rockchip', text)
        self.assertNotIn('backend auto', text)
        self.assertEqual(tree.getroot().tag, 'interfaceDefinition')

    def test_ustreamer_quality_is_fixed_to_80_and_not_cli_visible(self):
        xml = (ROOT / 'profiles/kvm-cli/service_kvm-over-ip.xml').read_text()
        conf = (ROOT / 'tools/kvm-cli/service_kvm_over_ip.py').read_text()
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()

        self.assertNotIn('leafNode name="quality"', xml)
        self.assertIn("'KVM_VIDEO_USTREAMER_QUALITY': '80'", conf)
        self.assertIn('KVM_VIDEO_USTREAMER_QUALITY:-80', runner)

    def test_provider_specific_implementations_remain_internal(self):
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()

        self.assertIn('/usr/local/bin/ffmpeg-rockchip', runner)
        self.assertIn('h264_rkmpp', runner)
        self.assertIn('mpph264enc', runner)
        self.assertIn('/usr/bin/ffmpeg', runner)
        self.assertIn('libx264', runner)

    def test_rock_hdmi_rx_syncs_detected_dv_timings(self):
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()

        self.assertIn('sync_provider_capture_timings', runner)
        self.assertIn('rk3588-synopsys-hdmirx', runner)
        self.assertIn(
            'v4l2-ctl -d "${DEVICE}" --set-dv-bt-timings query', runner
        )

    def test_reference_and_configd_integration_is_installed(self):
        installer = (ROOT / 'tools/install-kvm-cli.sh').read_text()
        merger = (ROOT / 'tools/kvm-cli/merge-vyos-reference.py').read_text()
        assemble = (ROOT / 'tools/assemble-board-image.sh').read_text()

        self.assertIn('vyos-kvm-merge-reference', installer)
        self.assertIn('configd-include.json', merger)
        self.assertIn('vyos.xml_ref.cache', merger)
        self.assertIn('tree_merge', merger)
        self.assertIn('KVM_CLI_INSTALLER', assemble)

    def test_gstreamer_rtsp_publisher_dependency_is_present(self):
        packages = (ROOT / 'profiles/kvm-over-ip-packages.txt').read_text()
        self.assertIn('gstreamer1.0-rtsp', packages)

    def test_scripts_parse(self):
        subprocess.run(
            ['bash', '-n', str(ROOT / 'tools/install-kvm-cli.sh')],
            check=True,
        )
        subprocess.run(
            ['bash', '-n', str(ROOT / 'tools/kvm-cli/vyos-kvm-video-runner')],
            check=True,
        )
        py_compile.compile(
            str(ROOT / 'tools/kvm-cli/service_kvm_over_ip.py'),
            doraise=True,
        )
        py_compile.compile(
            str(ROOT / 'tools/kvm-cli/merge-vyos-reference.py'),
            doraise=True,
        )


if __name__ == '__main__':
    unittest.main()
