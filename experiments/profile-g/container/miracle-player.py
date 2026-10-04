#!/usr/bin/python3
"""MiracleCast player with reconnectable MPEG-TS tracks and shared A/V clock."""
import argparse
import os
import json
from pathlib import Path
import signal
import sys
sys.path.insert(0, '/opt/profile-g')
from backend import config, gst_decoder, receiver_environment


def pipeline(port, audio, cfg):
    # Encoded queues provide headroom, without retaining decoder DMA buffers.
    queue = ['max-size-buffers=0', 'max-size-bytes=0', 'max-size-time=2000000000']
    args = ['udpsrc', f'port={port}', 'buffer-size=2097152',
            'caps=application/x-rtp,media=video,clock-rate=90000,encoding-name=MP2T,payload=33',
            '!', 'rtpjitterbuffer', 'latency='+cfg['latency'], 'drop-on-latency=false',
            '!', 'rtpmp2tdepay', '!', 'tsdemux', 'latency=200', 'name=demux',
            'queue', 'name=video_queue', *queue, '!', 'h264parse',
            '!', gst_decoder(cfg['decoder'], resolution=cfg.get('resolution', '1920x1080')), '!', 'waylandsink', 'name=video',
            'sync=true', 'enable-last-sample=false']
    if audio:
        args += ['queue', 'name=audio_queue', *queue, '!', 'aacparse', '!', 'avdec_aac',
                 '!', 'audioconvert', '!', 'audioresample', '!', 'pulsesink', 'name=audio',
                 'async=false', 'sync=true', 'buffer-time=200000', 'latency-time=20000']
    return args


class TrackLinks:
    """PMT updates can add a replacement pad before removing its predecessor."""
    def __init__(self, pipe):
        self.pipe = pipe
        self.demux = pipe.get_by_name('demux')
        self.handlers = [self.demux.connect('pad-added', self.added)]
        self.pids = {}
        self.error = None

    def added(self, demux, pad):
        # GI callbacks do not propagate exceptions to the application loop.
        try:
            self.link_pad(pad)
        except Exception as error:
            self.error = error

    def link_pad(self, pad):
        caps = pad.get_current_caps() or pad.query_caps(None)
        if caps.is_empty() or caps.is_any():
            return
        kind = caps.get_structure(0).get_name()
        branch = {'video/x-h264': 'video_queue', 'audio/mpeg': 'audio_queue'}.get(kind)
        queue = self.pipe.get_by_name(branch) if branch else None
        if queue is None:
            return
        # Keep the selected track; reconnect its new generation, not another PID.
        pid = pad.get_name().rsplit('_', 1)[-1]
        if branch in self.pids and self.pids[branch] != pid:
            return
        sink = queue.get_static_pad('sink')
        old = sink.get_peer()
        if old == pad:
            return
        if old:
            old.unlink(sink)
        result = pad.link(sink)
        if int(result) != 0:
            if old:
                old.link(sink)
            self.error = RuntimeError(f'Cannot link {pad.get_name()}: {result}')
            return
        self.pids[branch] = pid
        print(f'TRACK {pad.get_name()} -> {branch}', flush=True)

    def close(self):
        for handler in self.handlers:
            self.demux.disconnect(handler)


def play(args):
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst
    Gst.init(None)
    pipe = Gst.parse_launch(' '.join(args))
    tracks = TrackLinks(pipe)
    stopping = False
    def stop(*unused):
        nonlocal stopping
        stopping = True
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, stop)
    bus = pipe.get_bus()
    fullscreen = False
    reported = False
    stream = {'method': 'miracast', 'pid': os.getpid(), 'active': True,
              'actual_decoder': 'unknown', 'hardware_confirmed': False,
              'presentation_verified': False}
    def report():
        try:
            target = Path('/state/receiver-stream.json')
            temp = target.with_suffix('.tmp')
            temp.write_text(json.dumps(stream)+'\n')
            temp.replace(target)
        except OSError:
            pass  # Diagnostics must not interrupt playback.
    def decoded(pad, info):
        nonlocal reported
        if reported:
            return Gst.PadProbeReturn.OK
        iterator = pipe.iterate_recurse()
        decoders = []
        while True:
            result, element = iterator.next()
            if result != Gst.IteratorResult.OK:
                break
            factory = element.get_factory()
            if factory and 'Decoder/Video' in (factory.get_metadata('klass') or ''):
                decoders.append((factory.get_name(), 'Hardware' in (factory.get_metadata('klass') or '')))
        caps = pad.get_current_caps()
        stream.update(actual_decoder=[name for name, hw in decoders],
                      hardware_confirmed=any(hw for name, hw in decoders),
                      decoded_caps=caps.to_string() if caps else None)
        report(); reported = True
        return Gst.PadProbeReturn.OK
    pipe.get_by_name('video').get_static_pad('sink').add_probe(Gst.PadProbeType.BUFFER, decoded)
    report()
    try:
        if pipe.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError('Receiver failed to enter PLAYING')
        while not stopping:
            message = bus.timed_pop_filtered(Gst.SECOND,
                Gst.MessageType.ERROR | Gst.MessageType.EOS |
                Gst.MessageType.LATENCY | Gst.MessageType.CLOCK_LOST)
            if tracks.error is not None:
                raise tracks.error
            video = pipe.get_by_name('video')
            # Applying fullscreen before the Wayland window exists warns in 1.26.
            if not fullscreen and video.find_property('fullscreen') and video.get_property('stats').get_value('rendered'):
                video.set_property('fullscreen', True)
                fullscreen = True
            if message is None:
                continue
            if message.type == Gst.MessageType.ERROR:
                error, detail = message.parse_error()
                raise RuntimeError(f'{error}: {detail}')
            if message.type == Gst.MessageType.EOS:
                break
            if message.type == Gst.MessageType.LATENCY:
                pipe.recalculate_latency()
            if message.type == Gst.MessageType.CLOCK_LOST:
                pipe.set_state(Gst.State.PAUSED)
                pipe.set_state(Gst.State.PLAYING)
    finally:
        pipe.set_state(Gst.State.NULL)
        tracks.close()
        stream['active'] = False
        report()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', type=int, required=True)
    parser.add_argument('-a', action='store_true')
    for flag in ('-r', '-s', '-d'):
        parser.add_argument(flag)
    opts = parser.parse_args()
    if not 1024 <= opts.p <= 65535:
        parser.error('Invalid RTP port')
    if os.getuid() == 0:
        os.execvp('setpriv', ['setpriv', '--reuid=kiosk', '--regid=kiosk',
                   '--groups='+os.environ['G_DEVICE_GROUPS'], '--',
                   '/usr/bin/python3', os.path.realpath(__file__), *sys.argv[1:]])
    cfg = config()
    if opts.r:
        import re
        if not re.fullmatch(r'[1-9][0-9]{0,4}x[1-9][0-9]{0,4}', opts.r):
            parser.error('Invalid negotiated resolution')
        cfg['resolution'] = opts.r
    os.environ.update(receiver_environment(cfg))
    play(pipeline(opts.p, opts.a, cfg))
