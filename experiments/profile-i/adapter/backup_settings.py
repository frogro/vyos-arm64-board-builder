"""Scoped host configuration in media backups; never import arbitrary CLI."""
import io
import json
import os
import re
import tempfile
import time
import uuid
from pathlib import Path

MEMBER = 'vyarm-display.json'

def validate(value):
    if not isinstance(value, dict) or set(value)-{'rotation', 'output', 'muted', 'schedule', 'remote'} or not {'rotation','output','muted','schedule'} <= set(value):
        raise ValueError('Invalid display backup fields')
    if value['rotation'] not in ('0', '90', '180', '270'):
        raise ValueError('Invalid rotation')
    if not isinstance(value['output'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}', value['output']):
        raise ValueError('Invalid display output')
    if type(value['muted']) is not bool:
        raise ValueError('Invalid mute setting')
    if value['schedule'] is not None:
        import importlib.util
        spec = importlib.util.spec_from_file_location('backup_schedule', str(Path(__file__).parent/'f/kiosk-schedule.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        value = dict(value, schedule=module.validate(value['schedule']))
    if 'remote' in value:
        r=value['remote']
        if not isinstance(r,dict) or set(r)!={'access','input','audio','web_origin'}:raise ValueError('Invalid remote settings')
        for key,allowed in {'access':('enabled','disabled'),'input':('view-only','control'),'audio':('enabled','disabled')}.items():
            if r[key] not in allowed:raise ValueError('Invalid remote '+key)
        if not isinstance(r['web_origin'],list) or len(r['web_origin'])>16:raise ValueError('Invalid Web origins')
        for origin in r['web_origin']:
            if not isinstance(origin,str) or not re.fullmatch(r'https://(?:[A-Za-z0-9][A-Za-z0-9.-]*|\[[0-9a-fA-F:]+\])(?::[0-9]{1,5})?',origin):raise ValueError('Invalid HTTPS origin')
            from urllib.parse import urlsplit
            if urlsplit(origin).port == 0:raise ValueError('Invalid Web port')
    return value

def host_request(operation, settings=None):
    root = Path(os.environ.get('HOME', '/data'))
    job = {'id': uuid.uuid4().hex, 'operation': operation}
    if settings is not None:
        job.update(validate(settings))
    fd, name = tempfile.mkstemp(prefix='.display-', dir=root)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(job, stream)
        os.link(name, root/'i-display-request.json')
    finally:
        os.unlink(name)
    deadline = time.monotonic()+115
    while time.monotonic() < deadline:
        try:
            result = json.loads((root/'i-display-result.json').read_text())
            if result.get('id') == job['id']:
                if not result.get('ok'):
                    raise RuntimeError(result.get('error') or result.get('output') or 'Host configuration failed')
                return result.get('settings')
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.25)
    raise RuntimeError('Host configuration response timed out; check configuration before retrying')

def add_settings(tar):
    import tarfile
    settings = validate(host_request('export'))
    payload = json.dumps({'version': 1, 'settings': settings}).encode()
    member = tarfile.TarInfo(MEMBER)
    member.size = len(payload)
    tar.addfile(member, io.BytesIO(payload))

def read_settings(tar):
    members = [m for m in tar.getmembers() if m.name == MEMBER]
    if not members:
        return None  # Old backups leave the host configuration unchanged.
    if len(members) != 1 or not members[0].isfile() or members[0].size > 16384:
        raise ValueError('Invalid display backup member')
    value = json.load(tar.extractfile(members[0]))
    if not isinstance(value, dict) or set(value) != {'version', 'settings'} or type(value['version']) is not int or value['version'] != 1:
        raise ValueError('Unsupported display backup version')
    return validate(value['settings'])
