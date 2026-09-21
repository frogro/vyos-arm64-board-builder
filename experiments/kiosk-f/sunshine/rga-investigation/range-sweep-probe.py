#!/usr/bin/env python3
"""Bounded, synthetic RGA color test. Does not change the kiosk/container config.

Run on the host with access to its video devices and v4l2-ctl installed.
Exit 0: sampled colors pass; 1: mismatch; 2: no suitable device or probe error.
A pass alone does not establish latency, full color accuracy or integration.
"""
import argparse
import json
import hashlib
import math
import random
from pathlib import Path
import subprocess
import tempfile

WIDTH, HEIGHT = 1920, 1080
COLORS = [(0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
          (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255)]


def run(args):
    return subprocess.run(['v4l2-ctl', *args], check=True, timeout=15,
                          capture_output=True, text=True).stdout


def reference(rgb, kr, kb, full=False):
    r, g, b = rgb
    y = kr*r + (1-kr-kb)*g + kb*b
    if full:
        return [max(0, min(255, math.floor(v + .5))) for v in
                (y, 128 + (b-y)/(2*(1-kb)), 128 + (r-y)/(2*(1-kr)))]
    return [math.floor(v + .5) for v in
            (16 + y*219/255, 128 + (b-y)*112/((1-kb)*255),
             128 + (r-y)*112/((1-kr)*255))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extended', action='store_true',
                        help='Add gray ramps and compare against the requested range')
    parser.add_argument('--random-colors', action='store_true',
                        help='Test 120 reproducible RGB colors against the requested range')
    args = parser.parse_args()
    colors = COLORS + ([(v, v, v) for v in (16, 32, 64, 96, 128, 160, 192, 224)] if args.extended else [])
    if args.random_colors:
        rng = random.Random(20260921)
        colors = [tuple(rng.randrange(256) for _ in range(3)) for _ in range(120)]
    matched_range = args.extended or args.random_colors
    stripe = WIDTH // len(colors)
    # Restrict to the identified RGA driver; never probe capture/HDMI devices.
    candidates = [Path('/dev') / p.parent.name
                  for p in sorted(Path('/sys/class/video4linux').glob('video*/name'))
                  if p.read_text().strip() == 'rockchip-rga']
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one RGA device, found {len(candidates)}')
    device = str(candidates[0])
    info = run(['-d', device, '--info'])
    if 'Memory-to-Memory Multiplanar' not in info or 'Streaming' not in info:
        raise RuntimeError('Device lacks required mem2mem/streaming capabilities')
    for option, fourcc in [('--list-formats-out', 'XR24'), ('--list-formats', 'NV12')]:
        if fourcc not in run(['-d', device, option]):
            raise RuntimeError(f'Device lacks {fourcc}')
    report = {'device': device, 'width': WIDTH, 'height': HEIGHT, 'tests': []}
    if args.random_colors:
        report['random_seed'] = 20260921
    passed = True
    with tempfile.TemporaryDirectory(prefix='kiosk-rga-colors-') as tmp:
        source = Path(tmp) / 'bars.bgr0'
        target = Path(tmp) / 'bars.nv12'
        row = b''.join(bytes((b, g, r, 0))*stripe for r, g, b in colors)
        source.write_bytes(row*HEIGHT)
        for space, kr, kb, output_range in [(s,k,b,q) for s,k,b in [('smpte170m', .299, .114), ('rec709', .2126, .0722)] for q in ['lim-range','full-range']]:
            fmt = f'width={WIDTH},height={HEIGHT},'
            output = run(['-d', device,
                          '--set-fmt-video-out=' + fmt + 'pixelformat=XR24,colorspace=' + space + ',quantization=full-range',
                          '--set-fmt-video=' + fmt + 'pixelformat=NV12,colorspace=' + space + ',quantization=' + output_range,
                          '--get-fmt-video', '--stream-out-mmap=3', '--stream-mmap=3',
                          '--stream-count=1', '--stream-poll',
                          '--stream-from=' + str(source), '--stream-to=' + str(target)])
            # This probe only interprets tightly packed single-plane NV12.
            if f'Bytes per Line : {WIDTH}' not in output:
                raise RuntimeError('Unexpected output stride')
            data = target.read_bytes()
            if len(data) != WIDTH*HEIGHT*3//2:
                raise RuntimeError('Unexpected output size')
            samples = []
            for i, rgb in enumerate(colors):
                x = i*stripe + stripe//2
                y_index = (HEIGHT//2)*WIDTH+x
                uv_index = WIDTH*HEIGHT + (HEIGHT//4)*WIDTH+x
                actual = [data[y_index], data[uv_index], data[uv_index+1]]
                expected = reference(rgb, kr, kb, matched_range and output_range == "full-range")
                error = max(abs(a-b) for a, b in zip(actual, expected))
                passed &= error <= 3
                samples.append(dict(rgb=rgb, actual=actual, expected=expected, max_error=error))
            report['tests'].append(dict(colorspace=space, requested_range=output_range, reference_range=('full' if matched_range and output_range == 'full-range' else 'limited'), output_sha256=hashlib.sha256(data).hexdigest(),
                                        negotiated_format=output, samples=samples))
    report['passed'] = passed
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({'error': str(error)}))
        raise SystemExit(2)
