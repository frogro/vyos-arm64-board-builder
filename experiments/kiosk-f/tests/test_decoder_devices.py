import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import struct
import errno
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('kiosk', Path(__file__).resolve().parents[1] / 'cli/kiosk.py')
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)

class DecoderDevices(unittest.TestCase):
    def test_ioctl_rejects_capture_and_encoder_accepts_request_decoder(self):
        def check(flags, fourcc):
            def ioctl(fd, request, data, mutate):
                if request == 0x80685600:
                    struct.pack_into('II', data, 84, 0x80000000, flags)
                elif request == 0xc0405602:
                    index, queue = struct.unpack_from('II', data)
                    if index or queue != 10:
                        raise OSError()
                    data[44:48] = fourcc
                else:
                    self.fail('Discovery must not allocate or stream')
            with patch.object(kiosk.fcntl, 'ioctl', side_effect=ioctl):
                return kiosk.request_decoder('/dev/null')
        self.assertFalse(check(1, b'S264'))
        self.assertFalse(check(0x4000, b'NV12'))
        self.assertTrue(check(0x4000, b'S265'))

    def test_number_independent_and_only_matching_media(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); sys=root/'sys'; dev=root/'dev'; dev.mkdir()
            for video,media in [('video47','media9'),('video2','media1'),('video5','media3')]:
                (sys/video/'device'/media).mkdir(parents=True)
                (dev/video).symlink_to('/dev/null'); (dev/media).symlink_to('/dev/null')
            found=kiosk.decoder_devices(sys,dev,lambda p: p.endswith(('video47','video5')))
            self.assertEqual(set(found),{(str(dev/p),str(dev/p)) for p in ('video47','media9','video5','media3')})
    def test_missing_media_and_failed_probe_are_not_granted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); sys=root/'sys';dev=root/'dev';dev.mkdir()
            (sys/'video4'/'device').mkdir(parents=True);(dev/'video4').symlink_to('/dev/null')
            self.assertEqual(kiosk.decoder_devices(sys,dev,lambda _:True),[])
            def fail(_): raise PermissionError()
            self.assertEqual(kiosk.decoder_devices(sys,dev,fail),[])
    def test_explicit_devices_preserved_deduplicated_without_config_mutation(self):
        c={'kiosk':{'video_decode':'auto'},'device':{'media':{'source':'/dev/media9','destination':'/dev/media9'}}}
        before=copy.deepcopy(c)
        result=kiosk.devices(c,discover=lambda:[('/dev/media9','/dev/media9'),('/dev/video47','/dev/video47')])
        self.assertEqual(result,[('/dev/media9','/dev/media9'),('/dev/video47','/dev/video47')]); self.assertEqual(c,before)
    def test_conflict_rejected(self):
        c={'kiosk':{'video_decode':'auto'},'device':{'other':{'source':'/dev/video9','destination':'/dev/video47'}}}
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            kiosk.devices(c,discover=lambda:[('/dev/video47','/dev/video47')])
    def test_non_kiosk_legacy_software_do_not_probe(self):
        for c in ({},{'kiosk':{}},{'kiosk':{'video_decode':'software'}}):
            self.assertEqual(kiosk.devices(c,discover=lambda:self.fail('Unexpected probe')),[])

    def test_h264_size_ioctl_discrete_stepwise_and_unsupported(self):
        for kind, expected in ((1, (1920, 1080)), (2, (3840, 2160)),
                               (3, (3840, 2160)), (0, (0, 0))):
            def ioctl(fd, request, data, mutate):
                self.assertEqual(request, 0xc02c564a)
                self.assertEqual(bytes(data[4:8]), b'S264')
                if struct.unpack_from('I', data)[0] or not kind:
                    raise OSError(errno.EINVAL, 'end')
                struct.pack_into('I', data, 8, kind)
                if kind == 1:
                    struct.pack_into('II', data, 12, 1920, 1080)
                else:
                    struct.pack_into('IIIIII', data, 12, 48, 3840, 16, 48, 2160, 16)
            with patch.object(kiosk.fcntl, 'ioctl', side_effect=ioctl):
                self.assertEqual(kiosk.h264_limit('/dev/null'), expected)

    def test_uhd_priority_preserves_codecs_capture_aliases_and_saved_config(self):
        found = [(p,p) for p in ('/dev/video0','/dev/video12','/dev/video5','/dev/media0','/dev/media2')]
        c={'kiosk':{'video_decode':'auto'}, 'device':{
            'capture':{'source':'/dev/video3','destination':'/dev/video3'},
            'alias':{'source':'/dev/video0','destination':'/dev/hantro'},
            'explicit':{'source':'/dev/video12','destination':'/dev/video12'}}}
        before=copy.deepcopy(c)
        limits={'/dev/video0':(1920,1088),'/dev/video12':(3840,2160),'/dev/video5':(0,0)}
        result=kiosk.devices(c,discover=lambda:found,
                            rank=lambda b,d:kiosk.prioritize_h264(b,d,limits.__getitem__))
        self.assertIn(('/dev/video12','/dev/video0'),result)
        self.assertIn(('/dev/video0','/dev/video12'),result)
        for pair in [('/dev/video5','/dev/video5'),('/dev/video3','/dev/video3'),
                     ('/dev/video0','/dev/hantro'),('/dev/media0','/dev/media0')]:
            self.assertIn(pair,result)
        self.assertEqual(len(result),len({dst for _,dst in result}))
        self.assertEqual(c,before)

    def test_priority_is_stable_when_already_correct_or_capabilities_unknown(self):
        bindings=[('/dev/video2','/dev/video2'),('/dev/video47','/dev/video47')]
        for probe in (lambda p:(3840,2160) if p.endswith('2') else (1920,1088),
                      lambda p:(0,0),lambda p:(1920,1088)):
            self.assertEqual(kiosk.prioritize_h264(bindings,bindings,probe),bindings)
        def fail(_):raise PermissionError()
        self.assertEqual(kiosk.prioritize_h264(bindings,bindings,fail),bindings)

if __name__=='__main__': unittest.main()
