"""ISO upgrades and rollbacks select their own bundled kiosk runtime."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_kiosk', BASE / 'cli/kiosk.py')
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)


class RuntimeUpdate(unittest.TestCase):
    def test_upgrade_and_rollback_preserve_settings_and_saved_config(self):
        saved = {'name': {'signage': {'image': 'localhost/vyarm-kiosk:github-100',
                 'kiosk': {'url': 'http://127.0.0.1:8089/player', 'rotation': '90'},
                 'volume': {'state': {'source': '/config/signage/state'}}}}}
        original = copy.deepcopy(saved)
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'runtime.json'
            for version in (200, 90):
                manifest.write_text(json.dumps({'image': f'localhost/vyarm-kiosk:github-{version}',
                                               'image_id': 'sha256:' + 'a'*64}))
                candidate = copy.deepcopy(saved)
                kiosk.runtime_images(candidate, manifest)
                self.assertEqual(candidate['name']['signage']['image'],
                                 f'localhost/vyarm-kiosk:github-{version}')
                self.assertEqual(candidate['name']['signage']['kiosk'], saved['name']['signage']['kiosk'])
                self.assertEqual(candidate['name']['signage']['volume'], saved['name']['signage']['volume'])
        self.assertEqual(saved, original)

    def test_custom_images_and_non_kiosk_containers_are_untouched(self):
        config = {'name': {'custom': {'kiosk': {}, 'image': 'localhost/vyarm-kiosk:custom'},
                          'other': {'image': 'localhost/vyarm-kiosk:github-100'}}}
        original = copy.deepcopy(config)
        kiosk.runtime_images(config, Path('/nonexistent/manifest'))
        self.assertEqual(config, original)

    def test_missing_or_invalid_manifest_does_not_silently_run_old_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'runtime.json'
            for value in (None, '{', '{}', json.dumps({'image': 'external/untrusted:latest', 'image_id': 'a'*64})):
                if value is not None: manifest.write_text(value)
                with self.assertRaises(ValueError):
                    kiosk.runtime_images({'name': {'k': {'kiosk': {}, 'image': 'localhost/vyarm-kiosk:github-100'}}}, manifest)

    def test_candidate_and_effective_config_resolve_equally(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'runtime.json'
            manifest.write_text(json.dumps({'image': 'localhost/vyarm-kiosk:github-200', 'image_id': 'a'*64}))
            old = {'name': {'k': {'kiosk': {}, 'image': 'localhost/vyarm-kiosk:github-100'}}}
            new = {'name': {'k': {'kiosk': {}, 'image': 'localhost/vyarm-kiosk:github-200'}}}
            kiosk.runtime_images(old, manifest)
            kiosk.runtime_images(new, manifest)
            self.assertEqual(old, new)


if __name__ == '__main__':
    unittest.main()
