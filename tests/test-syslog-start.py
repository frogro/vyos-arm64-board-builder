#!/usr/bin/env python3
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('patcher', ROOT / 'tools/patch-vyos-syslog-start.py')
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)

class SyslogStart(unittest.TestCase):
    def test_timezone_preserved_without_starting_inactive_syslog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'usr/libexec/vyos/conf_mode/system_timezone.py'
            path.parent.mkdir(parents=True)
            path.write_text("def apply(tz):\n    call('/usr/bin/timedatectl set-timezone {}'.format(tz['name']))\n    call('systemctl restart rsyslog')\n")
            patcher.patch(root)
            first = path.read_text()
            patcher.patch(root)
            self.assertEqual(first, path.read_text())
            calls = []
            namespace = {'call': calls.append}
            exec(compile(ast.parse(first), str(path), 'exec'), namespace)
            namespace['apply']({'name': 'Europe/Berlin'})
            self.assertEqual(calls, ['/usr/bin/timedatectl set-timezone Europe/Berlin', 'systemctl try-restart rsyslog'])

    def test_unknown_upstream_fails_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'usr/libexec/vyos/conf_mode/system_timezone.py'
            path.parent.mkdir(parents=True)
            path.write_text('unknown implementation\n')
            with self.assertRaises(RuntimeError):
                patcher.patch(root)
            self.assertEqual(path.read_text(), 'unknown implementation\n')

if __name__ == '__main__':
    unittest.main()
