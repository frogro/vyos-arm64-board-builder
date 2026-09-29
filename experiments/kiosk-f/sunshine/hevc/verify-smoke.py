#!/usr/bin/env python3
"""Verify encode-smoke elementary streams using an independent FFmpeg decoder."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

results = {}
for filename in sys.argv[1:]:
    path = Path(filename)
    meta = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries',
        'stream=codec_name,width,height,pix_fmt,nb_read_frames,color_range,color_space',
        '-of', 'json', str(path)]))
    stream = meta['streams'][0]
    if (stream['width'], stream['height'], stream['nb_read_frames']) != (1920, 1080, '120'):
        raise SystemExit(f'{path}: unexpected dimensions or frame count')
    decoded = subprocess.run([
        'ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
        capture_output=True, text=True, check=True)
    raw = subprocess.check_output([
        'ffmpeg', '-v', 'error', '-i', str(path), '-vf',
        r'select=eq(n\,0)+eq(n\,119)', '-fps_mode', 'passthrough',
        '-pix_fmt', 'nv12', '-f', 'rawvideo', '-'])
    size = 1920 * 1080 * 3 // 2
    if len(raw) != 2 * size:
        raise SystemExit(f'{path}: unexpected decoded sample size')
    checks = []
    for index, frame in enumerate((0, 119)):
        errors = []
        for y in range(32, 1080, 64):
            for x in range(32, 1920, 64):
                if not 8 <= (x + frame * 8) % 120 <= 112:
                    continue
                expected = 16 + (((x + frame * 8) // 120) % 8) * 30
                errors.append(abs(raw[index * size + y * 1920 + x] - expected))
        uv = raw[index * size + 1920 * 1080:(index + 1) * size]
        checks.append(dict(frame=frame, sampled_luma_max_error=max(errors),
                           sampled_luma_mean_error=sum(errors) / len(errors),
                           chroma_max_error=max(abs(v - 128) for v in uv)))
    results[path.name] = dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                             bytes=path.stat().st_size, probe=meta,
                             decode_exit=decoded.returncode,
                             decode_stderr=decoded.stderr, reference_check=checks)
if not results:
    raise SystemExit('Usage: verify-smoke.py STREAM [STREAM ...]')
print(json.dumps(results, indent=2))
