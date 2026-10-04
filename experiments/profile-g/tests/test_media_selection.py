import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/profile-g/cli'),str(ROOT/'experiments/profile-g/container')]
import backend,receiver
spec=importlib.util.spec_from_file_location('g_media',ROOT/'experiments/profile-g/container/media.py')
media=importlib.util.module_from_spec(spec);spec.loader.exec_module(media)

class Selection(unittest.TestCase):
    def rows(self):
        return [{'factory':'v4l2slh264dec','device':'/dev/video9','sizes':[[48,1920,16,48,1088,16]]},
                {'factory':'v4l2slvideo1h264dec','device':'/dev/video1','sizes':[[1,4096,1,1,2304,1]]}]
    def test_node_order_does_not_select_small_decoder(self):
        for resolution in ('1920x1080','1920x1200','3840x2160'):
            result=media.select(self.rows(),resolution)
            self.assertEqual(result['selected'],'v4l2slvideo1h264dec')
        self.assertEqual(media.select(self.rows(),'3840x2160')['ranks']['v4l2slh264dec'],0)
    def test_coded_alignment_and_no_hardware(self):
        self.assertTrue(media.fits([48,1920,16,48,1088,16],1920,1080))
        self.assertFalse(media.fits([48,1920,16,48,1088,16],1920,1200))
        self.assertIsNone(media.select([],'3840x2160')['selected'])
        self.assertIsNone(media.select([dict(factory='x',sizes=[])],'3840x2160')['selected'])
    def test_hardware_does_not_fall_back_to_ineligible_stateless(self):
        with patch.object(backend,'gst_selection',return_value={'selected':None}),patch.object(backend.subprocess,'run') as run:
            run.return_value.returncode=1
            with self.assertRaises(ValueError):backend.gst_decoder('hardware',resolution='3840x2160')
            self.assertNotIn('v4l2slh264dec',[c.args[0][1] for c in run.call_args_list])
    def test_rank_merge_preserves_unrelated_override(self):
        result={'ranks':{'a':0,'b':300}}
        with patch.object(backend,'gst_selection',return_value=result):
            env=backend.gst_environment(dict(decoder='auto',resolution='3840x2160'),{'GST_PLUGIN_FEATURE_RANK':'a:999,c:123'})
        self.assertEqual(env['GST_PLUGIN_FEATURE_RANK'],'c:123,a:0,b:300')
    def test_auto_codec_is_explicit_h264_only_with_private_library(self):
        for decoder in ('auto','hardware','software'):
            cfg=receiver.settings(dict(method='moonlight',host='example.invalid',decoder=decoder,codec='auto'))
            cmd=backend.command(cfg)
            self.assertEqual(cmd[cmd.index('--video-codec')+1],'auto' if decoder=='software' else 'H.264')
            self.assertEqual('LD_LIBRARY_PATH' in backend.receiver_environment(cfg,{}),decoder!='software')
        cfg=receiver.settings(dict(method='moonlight',host='example.invalid',codec='hevc'))
        self.assertIn('LD_LIBRARY_PATH',backend.receiver_environment(cfg,{}))
        cfg['codec']='av1'
        self.assertNotIn('LD_LIBRARY_PATH',backend.receiver_environment(cfg,{}))
    def test_nv15_patch_is_part_of_build(self):
        script=(ROOT/'experiments/profile-g/container/build-ffmpeg-request.sh').read_text()
        self.assertIn('git apply --check /tmp/ffmpeg-rps/0003-nv15-uapi.patch',script)
        self.assertIn('v4l2-nv15-compat.h',script)
