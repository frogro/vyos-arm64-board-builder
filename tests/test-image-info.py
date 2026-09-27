#!/usr/bin/env python3
"""Regression: distinct numeric-looking image identifiers must remain distinct."""
import ast
import importlib.util
from pathlib import Path
import tempfile
import unittest
from tabulate import tabulate

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('image_info_patch', ROOT / 'tools/patch-vyos-image-info.py')
PATCHER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCHER)
SOURCE = (ROOT / 'tests/fixtures/image-info/image_info.py').read_text()
NAMES = ['999.202609230456', '999.202609210635', '000123', '1e10', 'rolling-test']


def renderers(source):
    ns = {'tabulate': tabulate, 'bytes_to_human': lambda value, **_: f'{value} KiB'}
    exec(compile(source, 'fixture', 'exec'), ns)
    return ns


class ImageInfoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / 'usr/libexec/vyos/op_mode/image_info.py'
        self.target.parent.mkdir(parents=True)
        self.target.write_text(SOURCE)
        self.target.chmod(0o755)

    def test_reported_rounding_reproduced_and_both_views_keep_identifiers(self):
        summary = {'images_available': NAMES[:2], 'image_default': NAMES[0], 'image_running': NAMES[0]}
        original = renderers(SOURCE)['_format_show_images_summary'](summary)
        self.assertEqual(original.count('999.203'), 2)
        self.assertTrue(PATCHER.patch(self.root))
        funcs = renderers(self.target.read_text())
        # Test numeric-only tables too: a text name in the column can itself
        # prevent tabulate's inference and would hide the original regression.
        for names in (NAMES[:2], NAMES):
            summary['images_available'] = names
            result = funcs['_format_show_images_summary'](summary)
            self.assertEqual([line.split()[0] for line in result.splitlines()[2:]], names)
            self.assertEqual(result.splitlines()[2].split()[1:], ['Yes', 'Yes'])
            details = [dict(name=n, version=n, disk_ro=12, disk_rw=3, disk_total=15) for n in names]
            result = funcs['_format_show_images_details'](details)
            self.assertEqual(len(result.splitlines()[2:]), len(names))
            for line, name in zip(result.splitlines()[2:], names):
                self.assertEqual(line.split()[:2], [name, name])
                self.assertIn('12 KiB', line)
                self.assertIn('15 KiB', line)
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o755)

    def test_only_numparse_keywords_change_and_second_run_is_noop(self):
        PATCHER.patch(self.root)
        fixed = self.target.read_text()
        tree = ast.parse(fixed)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tabulate':
                node.keywords = [k for k in node.keywords if k.arg != 'disable_numparse']
        self.assertEqual(ast.dump(tree), ast.dump(ast.parse(SOURCE)))
        self.assertFalse(PATCHER.patch(self.root))
        self.assertEqual(fixed, self.target.read_text())

    def test_multiline_trailing_comma_and_partly_upstream_fixed(self):
        self.target.write_text(SOURCE.replace('tabulate(table_data, headers)', 'tabulate(\n        table_data,\n        headers,\n    )'))
        PATCHER.patch(self.root)
        self.assertFalse(PATCHER.patch(self.root))
        self.target.write_text(SOURCE.replace('tabulate(table_data, headers)', 'tabulate(table_data, headers, disable_numparse=True)'))
        self.assertTrue(PATCHER.patch(self.root))
        self.assertFalse(PATCHER.patch(self.root))

    def test_unknown_upstream_fails_without_partial_write(self):
        for broken in [SOURCE.replace('_format_show_images_details', '_changed_details'),
                       SOURCE.replace('colalign=', 'unexpected_argument='),
                       SOURCE.replace('tabulate(table_data, headers)', 'tabulate(table_data, headers, disable_numparse=False)')]:
            with self.subTest(source=broken):
                self.target.write_text(broken)
                with self.assertRaises(ValueError): PATCHER.patch(self.root)
                self.assertEqual(self.target.read_text(), broken)

    def test_patcher_is_unconditional_after_profile_package_install(self):
        source = (ROOT / 'tools/assemble-board-image.sh').read_text()
        call = 'python3 "$IMAGE_INFO_PATCHER" "$SQUASH_ROOT"'
        self.assertEqual(source.count(call), 1)
        self.assertGreater(source.index(call), source.index('"$KVM_CLI_INSTALLER" "$SQUASH_ROOT"'))
        self.assertLess(source.index(call), source.index('===== BUILDING MATCHING VYOS INITRAMFS ====='))


if __name__ == '__main__':
    unittest.main()
