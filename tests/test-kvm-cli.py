#!/usr/bin/env python3

from pathlib import Path
import py_compile
import subprocess
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


class KvmCliTests(unittest.TestCase):
    def test_negotiated_conversion_preserves_legacy_and_falls_back_safely(self):
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()
        start = runner.index('            # Negotiated mode must not')
        end = runner.index('            # Opt-in negotiated CPU fallback', start)
        block = runner[start:end]
        for mode, enabled, converter, expected in [
            ('legacy', False, 'v4l2convert', 'v4l2convert'),
            ('negotiated', False, 'v4l2convert', 'videoconvert'),
            ('negotiated', True, 'v4l2convert', 'v4l2convert'),
            ('negotiated', True, 'videoconvert', 'videoconvert'),
        ]:
            script = ('COLORIMETRY=' + mode + '; converter=' + converter + '; '
                      + 'grep() { return ' + ('0' if enabled else '1') + '; };\n'
                      + block + '\nprintf "%s" "$converter"')
            result = subprocess.run(['bash', '-c', script], capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout, expected)

    def test_cached_copy_is_opt_in_and_keeps_rga_and_missing_helper_fallback(self):
        import tempfile
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()
        start = runner.index('            # Opt-in negotiated CPU fallback')
        end = runner.index('\n        fi', start)
        block = runner[start:end]
        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / 'helper'
            helper.write_text('#!/bin/sh\n')
            for mode, converter, fourcc, present, selected in [
                ('negotiated', 'videoconvert', 'BGR3', True, True),
                ('negotiated', 'videoconvert', 'RGB3', True, True),
                ('legacy', 'videoconvert', 'BGR3', True, False),
                ('negotiated', 'v4l2convert', 'BGR3', True, False),
                ('negotiated', 'videoconvert', 'YUYV', True, False),
                ('negotiated', 'videoconvert', 'BGR3', False, False),
            ]:
                helper.chmod(0o755 if present else 0o644)
                code = (f'COLORIMETRY={mode}; converter={converter}; FOURCC={fourcc}; '
                        'GST=original; args=();\n' + block.replace(
                            '/usr/libexec/vyos/vyos-kvm-cached-launch', str(helper)) +
                        '\nprintf "%s\\n" "$GST" "${args[@]}"')
                result = subprocess.run(['bash', '-c', code], text=True,
                                        capture_output=True, check=True).stdout
                self.assertEqual('name=vyarm_cached_copy' in result, selected)
                self.assertEqual(result.splitlines()[0], str(helper) if selected else 'original')

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

    def test_ustreamer_uses_selected_capture_format(self):
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()
        start = runner.index('        # HDMI RX can expose')
        end = runner.index('        [[ -n "${RESOLUTION}" ]] && args+=(--resolution=')
        block = runner[start:end]
        for detected, expected in [('bgr24', '--format=BGR24'),
                                   ('mjpeg', '--format=MJPEG'),
                                   ('yuyv422', '--format=YUYV')]:
            script = ('args=(); DEVICE=/dev/video9; '
                      'detect_ffmpeg_input_format() { echo ' + detected + '; };\n'
                      + block + '\nprintf "%s" "${args[@]}"')
            result = subprocess.run(['bash', '-c', script], capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout, expected)

    def test_capture_buffers_limited_only_for_internal_hdmi(self):
        runner = (ROOT / 'tools/kvm-cli/vyos-kvm-video-runner').read_text()
        start = runner.index('        # HDMI-RX has a bounded')
        end = runner.index('        [[ -n "${INPUT_FORMAT}" ]]', start)
        for source, expected in [('rk3588-synopsys-hdmirx', '-capture_buffers 4'),
                                 ('generic-v4l2', '')]:
            code = 'args=(); SOURCE_PROVIDER=' + source + ';\n' + runner[start:end]
            code += '\nprintf "%s" "${args[*]}"'
            result = subprocess.run(['bash', '-c', code], capture_output=True,
                                    text=True, check=True)
            self.assertEqual(result.stdout, expected)

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

    def test_reference_and_configd_come_from_source_build(self):
        installer = (ROOT / 'tools/install-kvm-cli.sh').read_text()
        prepare = (ROOT / 'tools/prepare-vyos-1x-profile.py').read_text()
        builder = (ROOT / 'tools/build-vyos-1x-profile.py').read_text()
        self.assertIn('interface-definitions/service_kvm-over-ip.xml.in', prepare)
        self.assertIn('dpkg-buildpackage -b -us -uc', builder)
        self.assertIn('configd-include.json', builder)
        self.assertNotIn('merge-vyos-reference', installer)

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



if __name__ == '__main__':
    unittest.main()
