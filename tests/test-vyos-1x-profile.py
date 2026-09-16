#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_profile',ROOT/'tools/prepare-vyos-1x-profile.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
    def source(self,d):
        p=Path(d);(p/'debian').mkdir();(p/'data').mkdir()
        (p/'debian/rules').write_text('override_dh_gencontrol:\n\tdh_gencontrol -- -v$(BASE_VERSION)-$(COMMIT_ID)\noverride_dh_auto_build:\n\tmake all\n')
        (p/'src/ocaml').mkdir(parents=True)
        (p/'src/ocaml/vyos_op_run.ml').write_text('check_command_permissions permissions args;\n    Unix.setuid 0;')
        (p/'debian/vyos-1x.postinst').write_text('#!/bin/bash\n# existing upstream steps\n')
        return p
    def test_base_is_byte_for_byte_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.source(d);before={str(x):x.read_bytes() for x in p.rglob('*') if x.is_file()}
            self.assertIsNone(m.prepare(p,'999.0-14891-gd185906f3',False))
            self.assertEqual(before,{str(x):x.read_bytes() for x in p.rglob('*') if x.is_file()})
    def test_kvm_uses_source_inputs_not_generated_cache_edits(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.source(d);meta=m.prepare(p,'999.0-14891-gd185906f3',True)
            self.assertTrue((p/'interface-definitions/service_kvm-over-ip.xml.in').exists())
            self.assertFalse((p/'templates-cfg').exists());self.assertFalse((p/'data/reftree.cache').exists())
            self.assertIn('\tmake all', (p/'debian/rules').read_text())
            self.assertIn(meta['package_version'],(p/'debian/rules').read_text())
            self.assertIn('/usr/libexec/vyos/vyos-kvm-input.py',(p/'src/systemd/vyos-kvm-input.service').read_text())
            self.assertIn('/usr/libexec/vyos/vyos-kvm-video-runner.sh',(p/'src/systemd/vyos-kvm-video.service').read_text())
    def test_refuses_dirty_or_unknown_base(self):
        for version in ['rolling','999.0-123-gabcdef1-dirty','999.0-123-gabcdef1+kvm.old']:
            with tempfile.TemporaryDirectory() as d, self.assertRaises(ValueError):m.prepare(self.source(d),version,True)
    def test_independent_and_combined_profiles(self):
        for kvm,tailscale in [(False,True),(True,False),(True,True)]:
            with self.subTest(kvm=kvm,tailscale=tailscale), tempfile.TemporaryDirectory() as d:
                p=self.source(d);meta=m.prepare(p,'999.0-14891-gd185906f3',kvm,tailscale)
                self.assertEqual((p/'interface-definitions/service_kvm-over-ip.xml.in').exists(),kvm)
                self.assertEqual((p/'interface-definitions/service_tailscale.xml.in').exists(),tailscale)
                self.assertEqual((p/'src/systemd/vyos-arm64-tailscaled.service').exists(),tailscale)
                self.assertEqual('tailscale-subnet-router' in meta['profiles'],tailscale)
                self.assertEqual('kvm-over-ip' in meta['profiles'],kvm)
    def test_operator_runner_install_is_restored_once(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.source(d)
            m.prepare(p,'999.0-14891-gd185906f3',True)
            path, script=m.restore_operator_runner_install(p)
            self.assertEqual(script.count('chmod u+s /usr/bin/vyos-op-run'),1)
            self.assertIn('# existing upstream steps',script)
            self.assertEqual(script,path.read_text())
    def test_changed_runner_requires_review(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.source(d)
            (p/'src/ocaml/vyos_op_run.ml').write_text('different implementation')
            with self.assertRaisesRegex(ValueError,'permission review'):
                m.prepare(p,'999.0-14891-gd185906f3',True)
            self.assertFalse((p/'interface-definitions').exists())
    def test_refuses_existing_extension(self):
        with tempfile.TemporaryDirectory() as d:
            p=self.source(d);m.prepare(p,'999.0-14891-gd185906f3',True)
            with self.assertRaises(ValueError):m.prepare(p,'999.0-14891-gd185906f3',True)
    def test_package_install_precedes_board_patches(self):
        s=(ROOT/'tools/assemble-board-image.sh').read_text()
        self.assertLess(s.index('"$KVM_CLI_INSTALLER" "$SQUASH_ROOT" "$KVM_CLI_ARTIFACTS"'),s.index('python3 "$ARM_CPU_OPMODE_PATCHER"'))
        installer=(ROOT/'tools/install-kvm-cli.sh').read_text()
        self.assertNotIn('merge-vyos-reference',installer)
        self.assertNotIn('write_node',installer)
        self.assertIn("'--install'",installer)
if __name__=='__main__': unittest.main()
