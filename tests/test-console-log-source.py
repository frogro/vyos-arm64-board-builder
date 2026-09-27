#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare',ROOT/'tools/prepare-vyos-1x-profile.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ConsoleLog(unittest.TestCase):
    def fixture(self, directory):
        root=Path(directory);p=root/'op-mode-definitions';p.mkdir()
        def definition(top, command):
            return f'''<interfaceDefinition><node name="{top}"><children>
      <node name="log"><children><leafNode name="console-server"><command>{command}</command></leafNode></children>
      </node>
      <node name="console-server"><children><leafNode name="ports"><command>console -x</command></leafNode></children></node>
</children></node></interfaceDefinition>'''
        (p/'show-console-server.xml.in').write_text(definition('show','journalctl --no-hostname --boot --follow --unit conserver-server.service'))
        (p/'show-log.xml.in').write_text(definition('show','journalctl --no-hostname --boot --unit conserver-server.service'))
        (p/'monitor-log.xml.in').write_text(definition('monitor','journalctl --no-hostname --follow --boot --unit conserver-server.service'))
        return root,p
    def test_removes_only_duplicate_and_accepts_already_fixed(self):
        with tempfile.TemporaryDirectory() as d:
            root,p=self.fixture(d)
            before={f.name:f.read_bytes() for f in p.iterdir()}
            path,text=m.remove_duplicate_console_log(root)
            self.assertNotIn('<node name="log">',text)
            self.assertIn('console -x',text)
            self.assertEqual(before,{f.name:f.read_bytes() for f in p.iterdir()})
            path.write_text(text)
            self.assertIsNone(m.remove_duplicate_console_log(root))
            self.assertEqual((p/'show-log.xml.in').read_bytes(),before['show-log.xml.in'])
            self.assertEqual((p/'monitor-log.xml.in').read_bytes(),before['monitor-log.xml.in'])
    def test_refuses_changed_canonical_command(self):
        with tempfile.TemporaryDirectory() as d:
            root,p=self.fixture(d);f=p/'show-log.xml.in';f.write_text(f.read_text().replace('--boot','--follow'))
            with self.assertRaisesRegex(ValueError,'Canonical'):m.remove_duplicate_console_log(root)
    def test_refuses_extra_command_in_duplicate_branch(self):
        with tempfile.TemporaryDirectory() as d:
            root,p=self.fixture(d);f=p/'show-console-server.xml.in'
            f.write_text(f.read_text().replace('</leafNode></children>','</leafNode><leafNode name="other"/></children>',1))
            with self.assertRaisesRegex(ValueError,'duplicate changed'):m.remove_duplicate_console_log(root)

if __name__=='__main__':unittest.main()
