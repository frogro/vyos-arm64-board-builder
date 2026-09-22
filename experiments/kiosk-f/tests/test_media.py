import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
media=load('media','container/kiosk-media.py')
cli=load('cli','cli/kiosk.py')
remote=load('remote','cli/remote.py')

class MediaTests(unittest.TestCase):
    def setUp(self):
        self.caps={'backend':'v4l2-request','verified_binary':True,'base_features':['AcceleratedVideoDecoder'], 'features':list(media.FEATURES.values())}
        self.devices={'decoder':['/dev/video47'],'media':['/dev/media9'],'render':['/dev/dri/renderD129']}
    def test_absent_preserves_legacy(self):
        args,status=media.plan({},self.caps,self.devices)
        self.assertEqual(args,[]);self.assertEqual(status['requested'],'legacy')
        self.assertFalse(status['hardware_confirmed'])
    def test_software_disables_hardware(self):
        args,status=media.plan({'KIOSK_VIDEO_DECODE':'software'},self.caps,self.devices)
        self.assertEqual(args,['--disable-accelerated-video-decode'])
    def test_missing_devices_not_success(self):
        for missing in self.devices:
            args,status=media.plan({'KIOSK_VIDEO_DECODE':'auto','KIOSK_VIDEO_AV1_BUFFERS':'enabled'},self.caps,{**self.devices,missing:[]})
            self.assertTrue(status['fallback_reason']);self.assertFalse(status['active_features'])
    def test_unverified_browser_no_force(self):
        args,status=media.plan({'KIOSK_VIDEO_DECODE':'auto'},dict(self.caps,verified_binary=False),self.devices)
        self.assertEqual(args,[]);self.assertTrue(status['fallback_reason'])
    def test_independent_reserves(self):
        for codec,feature in media.FEATURES.items():
            args,status=media.plan({'KIOSK_VIDEO_DECODE':'auto',f'KIOSK_VIDEO_{codec.upper()}_BUFFERS':'enabled'},self.caps,self.devices)
            self.assertEqual(status['active_features'],['AcceleratedVideoDecoder',feature])
            self.assertFalse(status['hardware_confirmed'])
    def test_reject_unsupported_strict_and_invalid_combination(self):
        for env in ({'KIOSK_VIDEO_DECODE':'hardware-required'}, {'KIOSK_VIDEO_AV1_BUFFERS':'enabled'}, {'KIOSK_VIDEO_DECODE':'software','KIOSK_VIDEO_H264_BUFFERS':'enabled'}):
            with self.assertRaises(ValueError): media.plan(env,self.caps,self.devices)
    def test_native_preserves_unrelated_and_absent(self):
        self.assertEqual(cli.environment({'image':'unrelated'}),[])
        settings={'url':'file:///a'}
        self.assertFalse(any('VIDEO_' in s for s in cli.environment({'kiosk':settings})))
        out=cli.environment({'kiosk':dict(settings,video_decode='auto',video_av1_buffers='enabled')})
        self.assertIn('Environment=KIOSK_VIDEO_AV1_BUFFERS="enabled"',out)
    def test_rejects_image_without_runtime_contract(self):
        config={'image':'test','kiosk':{'url':'file:///a','video_decode':'auto'}}
        with patch.object(remote.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps([{'Labels':{}}]),'')):
            with self.assertRaises(ValueError):remote.verify_image(config)
        labels={'io.vyarm.kiosk.media-policy':'1'}
        with patch.object(remote.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps([{'Labels':labels}]),'')):
            remote.verify_image(config)
            config['kiosk']['video_av1_buffers']='enabled'
            with self.assertRaises(ValueError):remote.verify_image(config)
    def test_supported_image_accepts_explicit_reserve(self):
        labels={'io.vyarm.kiosk.media-policy':'1','io.vyarm.kiosk.media-av1-reserve':'1'}
        config={'image':'test','kiosk':{'url':'file:///a','video_decode':'auto','video_av1_buffers':'enabled'}}
        with patch.object(remote.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps([{'Labels':labels}]),'')):
            remote.verify_image(config)
    def test_wayland_recipe_not_forced_on_x11(self):
        caps=dict(self.caps,graphics_backend='wayland')
        args,status=media.plan({'KIOSK_VIDEO_DECODE':'auto','DISPLAY':':0'},caps,self.devices)
        self.assertEqual(args,[]);self.assertEqual(status['active_features'],[])
        self.assertIn('Wayland',status['fallback_reason'])

    def test_no_false_remote_only_for_media_change(self):
        old={'kiosk':{'url':'file:///a','remote':{'audio':'disabled'}}}
        new={'kiosk':{'url':'file:///a','remote':{'audio':'disabled'},'video_decode':'auto'}}
        self.assertFalse(remote.remote_only(old,new))
        self.assertEqual(remote.policy(old),remote.policy(new))

if __name__=='__main__': unittest.main()
