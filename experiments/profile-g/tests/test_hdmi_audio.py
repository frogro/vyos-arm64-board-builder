import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('hdmi_audio',Path(__file__).resolve().parents[1]/'container/hdmi-audio.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Selection(unittest.TestCase):
    def test_edid_match_not_card_number_and_disconnect(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); drm=root/'drm'; sound=root/'sound'; output=drm/'card0-HDMI-A-2';output.mkdir(parents=True)
            (output/'status').write_text('connected')
            edid=bytearray(128);edid[:8]=b'\0\xff\xff\xff\xff\xff\xff\0';edid[8:12]=bytes.fromhex('4a8b32bc');(output/'edid').write_bytes(edid)
            card=sound/'card7';(card/'pcm0p').mkdir(parents=True)
            valid='manufacture_id 0x8b4a\nproduct_id 0xbc32\nsad_count 1\neld_version [0x2] CEA\n'
            (card/'eld#0').write_text(valid)
            pick=lambda:m.select_device('card0','HDMI-A-2',drm,sound)
            self.assertEqual(pick(),'plughw:7,0')
            (output/'status').write_text('disconnected');self.assertIsNone(pick())
            (output/'status').write_text('connected')
            (card/'eld#0').write_text(valid.replace('sad_count 1','sad_count 0'));self.assertIsNone(pick())
            (card/'eld#0').write_text(valid)
            other=sound/'card2';(other/'pcm0p').mkdir(parents=True);(other/'eld#0').write_text(valid)
            self.assertIsNone(pick())
            (other/'eld#0').write_text(valid.replace('0xbc32','0xabcd'))
            self.assertEqual(pick(),'plughw:7,0')
