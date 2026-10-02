#!/usr/bin/env python3
import importlib.util
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('builder', Path(__file__).resolve().parents[1]/'tools/build-vyos-1x-profile.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class Resolution(unittest.TestCase):
    def test_authenticated_and_anonymous_resolution(self):
        sha = 'a' * 40
        for env, expected in [({}, None), ({'GH_TOKEN': 'test-value'}, 'Bearer test-value'), ({'GITHUB_TOKEN': 'fallback'}, 'Bearer fallback')]:
            with patch.dict(m.os.environ, env, clear=True), patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'sha': sha}).encode())) as request:
                self.assertEqual(m.resolve('999.0-1-gaaaaaaa'), sha)
                self.assertEqual(request.call_args.args[0].get_header('Authorization'), expected)
    def test_mismatched_source_still_rejected(self):
        with patch.object(m.urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps({'sha':'b'*40}).encode())):
            with self.assertRaisesRegex(ValueError, 'Source commit mismatch'):
                m.resolve('999.0-1-gaaaaaaa')
if __name__ == '__main__': unittest.main()
