#!/usr/bin/env python3
"""Summarize measured whole-container CPU after five seconds of warmup."""
import json
import statistics
import sys
from pathlib import Path
root = Path(sys.argv[1])
rows = []
for path in sorted(root.glob('[123]-*.json')):
    data = json.loads(path.read_text())
    page = data['page']
    samples = [s for s in data['cpuSamples'] if s['state'] == 'playing']
    if not samples:
        raise ValueError(f'{path}: no playing CPU samples')
    steady = [s for s in samples if s['monotonic'] >= samples[0]['monotonic'] + 5]
    if len(steady) < 2:
        raise ValueError(f'{path}: insufficient steady playback')
    a, b = steady[0], steady[-1]
    seconds = b['monotonic'] - a['monotonic']
    cores = (b['usage_usec'] - a['usage_usec']) / 1e6 / seconds
    props = {}
    for e in data['mediaEvents']:
        for prop in e.get('params', {}).get('properties', []):
            props[prop['name']] = prop['value']
    row = dict(run=path.stem, state=page['state'], width=page.get('width'),
               height=page.get('height'), total=page.get('totalFrames'),
               dropped=page.get('droppedFrames'), elapsedMs=page.get('elapsedMs'),
               steadySeconds=round(seconds, 3), cpuOneCorePercent=round(cores*100, 2),
               decoder=props.get('kVideoDecoderName'),
               platform=props.get('kIsPlatformVideoDecoder'))
    rows.append(row)
result = {'scope': 'whole disposable browser + Weston + probe cgroup; 100% = one CPU core',
          'warmupSeconds': 5, 'runs': rows, 'medians': {}}
for codec in ('h264', 'hevc'):
    selected = [r for r in rows if r['run'].endswith(codec)]
    if selected:
        result['medians'][codec] = {key: statistics.median(r[key] for r in selected)
                                  for key in ('cpuOneCorePercent', 'dropped', 'elapsedMs')}
print(json.dumps(result, indent=2))
