import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
import struct
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

if __name__=='__main__': unittest.main()
