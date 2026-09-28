"""GStreamer regression: absent optional audio must not stall live video."""
import importlib.util
from pathlib import Path
import sys
import time
import unittest
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
except (ImportError, ValueError):
    Gst = None

@unittest.skipIf(Gst is None, 'Requires system Python GI/GStreamer')
class OptionalAudio(unittest.TestCase):
    def test_missing_audio_does_not_block_video(self):
        root = Path(__file__).resolve().parents[1]
        sys.path[:0] = [str(root/'container'), str(root/'cli')]
        spec = importlib.util.spec_from_file_location('miracle_player', root/'container/miracle-player.py')
        player = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(player)
        args = player.pipeline(7236, True, {'latency': '50', 'decoder': 'auto'})
        options = args[args.index('pulsesink')+1:]
        async_option = next(x for x in options if x.startswith('async='))
        Gst.init(None)
        if not all(Gst.ElementFactory.find(x) for x in ('videotestsrc', 'appsrc', 'fakesink')):
            self.skipTest('Requires GStreamer test elements')
        # The absent audio source supplies no preroll buffer; video must still flow.
        pipe = Gst.parse_launch('videotestsrc is-live=true ! fakesink name=video signal-handoffs=true '
                                'appsrc name=absent ! fakesink ' + async_option)
        frames = []
        pipe.get_by_name('video').connect('handoff', lambda *unused: frames.append(1))
        try:
            pipe.set_state(Gst.State.PLAYING)
            deadline = time.monotonic() + 2
            while len(frames) < 10 and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertGreaterEqual(len(frames), 10, 'Missing audio blocked live video')
        finally:
            pipe.set_state(Gst.State.NULL)

if __name__ == '__main__':
    unittest.main()
