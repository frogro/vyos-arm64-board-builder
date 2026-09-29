"""Exercise real Gst pad links during the observed PMT generation rollover."""
import importlib.util
from pathlib import Path
import sys
import unittest
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
except (ImportError, ValueError):
    Gst = None

@unittest.skipIf(Gst is None, 'Requires GI/GStreamer')
class TrackRollover(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        sys.path[:0] = [str(root/'container'), str(root/'cli')]
        spec = importlib.util.spec_from_file_location('player', root/'container/miracle-player.py')
        self.player = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.player)
        Gst.init(None)
        self.pipe = Gst.parse_launch('tsdemux name=demux queue name=video_queue ! fakesink queue name=audio_queue ! fakesink')
        self.links = self.player.TrackLinks(self.pipe)

    def tearDown(self):
        self.links.close()
        self.pipe.set_state(Gst.State.NULL)

    def pad(self, name, caps):
        template = Gst.PadTemplate.new(name, Gst.PadDirection.SRC, Gst.PadPresence.SOMETIMES, Gst.Caps.from_string(caps))
        return Gst.Pad.new_from_template(template, name)

    def test_replacement_before_old_removal(self):
        for branch, caps, prefix, pid in [('video_queue', 'video/x-h264', 'video', '1011'), ('audio_queue', 'audio/mpeg,mpegversion=4', 'audio', '1100')]:
            old = self.pad(f'{prefix}_0_{pid}', caps)
            new = self.pad(f'{prefix}_1_{pid}', caps)
            demux = self.pipe.get_by_name('demux')
            demux.add_pad(old)
            sink = self.pipe.get_by_name(branch).get_static_pad('sink')
            self.assertEqual(sink.get_peer(), old)
            demux.add_pad(new)
            self.assertFalse(old.is_linked())
            self.assertEqual(sink.get_peer(), new)
            demux.remove_pad(old)
            self.assertEqual(sink.get_peer(), new)
            self.assertIsNone(self.links.error)

    def test_other_track_does_not_replace_selected_pid(self):
        first = self.pad('video_0_1011', 'video/x-h264')
        other = self.pad('video_0_1012', 'video/x-h264')
        demux = self.pipe.get_by_name('demux')
        demux.add_pad(first)
        demux.add_pad(other)
        self.assertEqual(self.pipe.get_by_name('video_queue').get_static_pad('sink').get_peer(), first)
        self.assertFalse(other.is_linked())
