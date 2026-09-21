"""Validate completed live-test evidence, not a substitute for patch compilation."""
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
rows = json.loads((root / 'followup-results.json').read_text())
for row in rows:
    page = row['page']
    assert page['state'] == 'ended', row['run']
    assert not page.get('error'), row['run']
    assert row['allocation'], row['run']
    for line in row['allocation']:
        match = re.fullmatch(r'VYARM_CAPTURE requested=(\d+) override=(\d+) returned=(\d+) result=(\d+)', line)
        assert match, line
        requested, override, returned, result = map(int, match.groups())
        assert requested > 0 and override >= requested and returned == override and result == 0, line
    if row['run'].startswith('seek-range-'):
        assert len(page['cycles']) == 8
        assert all(abs(c['mediaTime'] - c['target']) <= .25 for c in page['cycles'])
    if row['run'].startswith('resolution-extra-'):
        assert [c['height'] for c in page['cycles']] == [1080, 720, 1080, 720, 1080]
        assert all(c['currentTime'] >= 1 and c['total'] > 0 for c in page['cycles'])
    if row['run'].startswith('webrtc-60-'):
        assert page['requestedSeconds'] == 60
        assert page['finalConnectionState'] == 'connected'
        inbound = [s for s in page['stats'] if s.get('type') == 'inbound-rtp']
        assert inbound and all(s['packetsLost'] == 0 and s['framesDecoded'] > 3000 for s in inbound)
print(f'{len(rows)} completed live-result records validated')
