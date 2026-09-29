import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/profile-g/container'),str(ROOT/'experiments/profile-g/cli')]
import steamlink
import receiver

class SteamTests(unittest.TestCase):
    def test_unknown_settings_preserved_and_repeated_update_stable(self):
        unknown=b'\xa2\x01\x03abc'+b'\xe5\x01\x00\x00\x80?'
        data=b'\x20\x1e'+unknown+b'\x68\x00'
        changed=steamlink.update_protobuf(data,{4:60,13:1})
        self.assertEqual(changed,unknown+b'\x20\x3c\x68\x01')
        self.assertEqual(steamlink.update_protobuf(changed,{4:60,13:1}),changed)
    def test_bad_state_is_not_overwritten(self):
        cfg=receiver.settings({'method':'steamlink'})
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'settings.bin';p.write_bytes(b'\xa2\x01\x7fabc')
            with self.assertRaises(ValueError):steamlink.configure(p,cfg,True)
            self.assertEqual(p.read_bytes(),b'\xa2\x01\x7fabc')
            self.assertFalse(p.with_suffix('.bin.before-profile-g').exists())
    def test_cli_overrides_keep_backup_and_pairing(self):
        cfg=receiver.settings({'method':'steamlink','codec':'hevc'})
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'streaming_settings.bin';p.write_bytes(b'\x08\x02')
            pairing=Path(t)/'client_id';pairing.write_text('paired')
            steamlink.configure(p,cfg,True)
            self.assertIn(b'\x68\x01',p.read_bytes())
            steamlink.configure(p,cfg,False)
            self.assertIn(b'\x68\x00',p.read_bytes())
            self.assertEqual(p.with_suffix('.bin.before-profile-g').read_bytes(),b'\x08\x02')
            self.assertEqual(pairing.read_text(),'paired')
    def test_auto_falls_back_but_hardware_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            env={'HOME':t,'XDG_RUNTIME_DIR':t,'PATH':'/usr/bin','PULSE_SERVER':'test'}
            with patch.object(steamlink,'digest',return_value=steamlink.SHELL_SHA256),patch.object(steamlink,'check_runtime',side_effect=ValueError('bad hash')):
                result=steamlink.launch_environment(receiver.settings({'method':'steamlink','codec':'hevc'}),env)
                self.assertNotIn('request-bridge',result['LD_PRELOAD'])
                self.assertNotIn('G_STEAMLINK_HEVC',result)
                self.assertEqual(result['PULSE_SERVER'],'test')
                with self.assertRaisesRegex(ValueError,'Hardware decoder refused'):
                    steamlink.launch_environment(receiver.settings({'method':'steamlink','decoder':'hardware'}),env)
    def test_wrong_shell_always_refused(self):
        with patch.object(steamlink,'digest',return_value='wrong'),self.assertRaisesRegex(ValueError,'Unsupported Steam'):
            steamlink.launch_environment(receiver.settings({'method':'steamlink','decoder':'software'}),{})
    def test_serialized_native_config_can_be_validated_again(self):
        cfg=receiver.settings({'method':'steamlink','codec':'hevc'})
        self.assertEqual(receiver.settings(cfg),cfg)

    def test_cli_rejects_unqualified_modes(self):
        for extra in ({'codec':'av1'},{'codec':'hevc','decoder':'software'},{'host':'legion'},{'fps':'120'},{'resolution':'3840x2160'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):receiver.settings(dict(method='steamlink',**extra))
        self.assertEqual(receiver.settings({'method':'steamlink','mode':'pair'})['mode'],'pair')
    def test_explicit_heap_and_runtime_capability(self):
        cfg={'receiver':{'method':'steamlink'},'capability':['mknod'],'allow_host_networks':{},'volume':{'state':{'source':'/config/g','destination':'/state'}},'device':{'drm':{'source':'/dev/dri/card0','destination':'/dev/dri/card0'}}}
        with self.assertRaisesRegex(ValueError,'heap'):receiver.environment(cfg)
        cfg['device']['heap']={'source':'/dev/dma_heap/system','destination':'/dev/dma_heap/system'}
        with self.assertRaisesRegex(ValueError,'pinned Steam'):
            receiver.verify_all({'name':{'g':cfg}},image_probe=lambda _:['airplay'])
        receiver.verify_all({'name':{'g':cfg}},image_probe=lambda _:['steamlink-experimental'])
    def test_iso_manifest_preserves_old_profiles_and_adds_g(self):
        # Run the actual embedded generator, not a copy of its feature logic.
        script=(ROOT/'tools/create-system-image-iso.sh').read_text()
        code=script.split('"${COMPATIBLE[@]}" <<\'PY\'\n',1)[1].split('\nPY',1)[0]
        import json
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'manifest.json'
            for g in ('no','yes'):
                args=['-',str(out),'rock-5b','ROCK 5B','rock.dtb','uefi','uefi-grub','network-tailscale-kvm-kiosk','yes','yes','yes','rockchip','v4l2','no','yes',g,'radxa,rock-5b','rockchip,rk3588']
                with patch.object(sys,'argv',args):exec(compile(code,'<iso-manifest>','exec'),{})
                value=json.loads(out.read_text())
                self.assertEqual(value['compatible'],['radxa,rock-5b','rockchip,rk3588'])
                self.assertEqual(value['features'],dict(extended_network=True,tailscale_subnet_router=True,kvm_over_ip=True,kiosk_f=True,**({'receiver_g':True} if g=='yes' else {})))

if __name__=='__main__':unittest.main()
