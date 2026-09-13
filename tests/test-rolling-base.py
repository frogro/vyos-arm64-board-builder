#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rolling', Path(__file__).resolve().parents[1] / 'tools/resolve-rolling-base.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
SHA = 'a' * 40
OTHER = 'b' * 40


class Selection(unittest.TestCase):
    def setUp(self):
        self.source = SHA
        self.recipe = m.recipe_hash()
        self.expired = False
        self.status = 'success'
        self.downloads = 0

    def gh(self, *args):
        if args[0] == 'run':
            self.downloads += 1
            target = Path(args[args.index('--dir') + 1])
            (target / 'vyos-source-commit.txt').write_text(self.source)
            if self.recipe is not None:
                (target / 'raw-recipe-sha256.txt').write_text(self.recipe)
            return ''
        url = args[-1]
        run = dict(id=42, conclusion=self.status, path='.github/workflows/test-vyos-arm64-raw.yml')
        if '/commits/' in url:
            return json.dumps({'sha': SHA})
        if url.endswith('/artifacts'):
            return json.dumps([{'artifacts': [dict(name=n, expired=self.expired)
                for n in ('vyos-arm64-raw', 'vyos-arm64-raw-provenance')]}])
        if '?' in url:
            return json.dumps({'workflow_runs': [run]})
        return json.dumps(run)

    def resolve(self, requested=''):
        with patch.object(m, 'gh', self.gh):
            return m.resolve('owner/repo', 'rolling', requested)

    def test_reuses_matching_snapshot_and_recipe(self):
        self.assertEqual(self.resolve()[:2], (SHA, '42'))

    def test_new_rolling_builds_fresh(self):
        self.source = OTHER
        self.assertEqual(self.resolve()[:2], (SHA, ''))

    def test_changed_recipe_builds_fresh(self):
        self.recipe = 'old'
        self.assertEqual(self.resolve()[1], '')

    def test_legacy_unattested_recipe_not_automatic(self):
        self.recipe = None
        self.assertEqual(self.resolve()[1], '')

    def test_explicit_source_attested_legacy_recipe_allowed(self):
        self.recipe = None
        self.assertEqual(self.resolve('42')[1], '42')

    def test_explicit_mismatch_fails(self):
        self.source = OTHER
        with self.assertRaises(ValueError):
            self.resolve('42')

    def test_expired_rebuilds_without_download(self):
        self.expired = True
        self.assertEqual(self.resolve()[1], '')
        self.assertEqual(self.downloads, 0)

    def test_failed_explicit_run_fails(self):
        self.status = 'failure'
        with self.assertRaises(ValueError):
            self.resolve('42')

    def test_api_failure_is_not_cache_miss(self):
        with patch.object(m, 'gh', side_effect=RuntimeError('API unavailable')):
            with self.assertRaises(RuntimeError):
                m.resolve('owner/repo', 'rolling')


if __name__ == '__main__':
    unittest.main()
