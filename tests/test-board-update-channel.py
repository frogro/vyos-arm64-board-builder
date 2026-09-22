#!/usr/bin/env python3
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('channel', ROOT/'tools/board-update-channel.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ChannelTests(unittest.TestCase):
    def test_only_registered_network(self):
        self.assertEqual(m.channel_for('radxa-e52c','network')['repository'],'VyARM-Community/radxa-e52c')
        self.assertEqual(m.channel_for('rock-5b','network')['repository'],'VyARM-Community/rock-5b')
        self.assertIsNone(m.channel_for('rock-5b','network-tailscale-kvm'))
        for board, profile in [('unknown-board','network'),('radxa-e52c','base'),('radxa-e52c','network-tailscale'),('radxa-e52c','network-tailscale-kvm')]:
            self.assertIsNone(m.channel_for(board,profile))

    def test_feed_and_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            iso=Path(d)/'test.iso';iso.write_bytes(b'test payload')
            Path(str(iso)+'.sha256').write_text(hashlib.sha256(iso.read_bytes()).hexdigest()+'  test.iso\n')
            manifest={'board':'radxa-e52c','profile':'network','architecture':'arm64'}
            out=Path(d)/'image-version.json'
            def prepare(data):
                return m.prepare('radxa-e52c','network',data,iso,'test-release','999.20260919',out)
            prepare(manifest)
            feed=json.loads(out.read_text())
            self.assertEqual(feed[0]['url'],'https://github.com/VyARM-Community/radxa-e52c/releases/download/test-release/test.iso')
            for field, value in [('board','rock-5b'),('profile','network-kvm'),('architecture','amd64')]:
                with self.assertRaises(ValueError): prepare({**manifest,field:value})
            iso.write_bytes(b'corrupt')
            with self.assertRaises(ValueError): prepare(manifest)

    def test_rootfs_channel_selection(self):
        source=(ROOT/'tools/finalize-vyos-rootfs.sh').read_text()
        block=source.split('# Only registered A+B images')[1].split('MULTI_USER_WANTS_DIR=')[0]
        block='# Only registered A+B images'+block
        with tempfile.TemporaryDirectory() as d:
            env={'ROOT':str(ROOT),'PROFILE_DIR':d,'BOARD':'radxa-e52c','BUILD_PROFILE':'network','PATH':'/usr/bin:/bin'}
            subprocess.run(['bash','-eu','-c',block],env=env,check=True)
            self.assertEqual(json.loads((Path(d)/'update-channel.json').read_text())['profile'],'network')
            for profile in ['network-tailscale','network-tailscale-kvm','base']:
                subprocess.run(['bash','-eu','-c',block],env={**env,'BUILD_PROFILE':profile},check=True)
                self.assertFalse((Path(d)/'update-channel.json').exists())

    def test_no_override_or_automatic_checks(self):
        source=(ROOT/'tools/common-firstboot/dhcp-wan-ssh-setup.sh').read_text()
        block=source.split('# Seed only fresh installations;')[1].split('if ! setup_commit_save')[0]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); channel=root/'channel.json'; channel.write_text(json.dumps({'url':'https://example.test/feed.json'}))
            block=block[block.index('CHANNEL_FILE='):].replace('/usr/share/vyos-arm64-board-builder/update-channel.json',str(channel)).replace('/config/.dhcp-wan-ssh-firstboot-done',str(root/'done'))
            api=root/'api';api.write_text('#!/bin/sh\nexit "${EXISTING:-1}"\n');api.chmod(0o755)
            setup='setup_set() { printf "%s\\n" "$*"; }; fail() { exit 1; };\n'
            def run(auto,exists):
                return subprocess.check_output(['bash','-eu','-c',setup+block],env={'PATH':'/usr/bin:/bin','AUTO_SETUP':auto,'EXISTING':str(exists),'API':str(api)},text=True)
            self.assertEqual(run('yes',1).strip(),'system update-check url https://example.test/feed.json')
            self.assertEqual(run('yes',0),'')
            self.assertEqual(run('no',1),'')
            (root/'done').touch();self.assertEqual(run('yes',1),'')

unittest.main()
