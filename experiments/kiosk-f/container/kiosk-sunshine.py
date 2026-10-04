#!/usr/bin/env python3
"""Local Sunshine supervisor/control socket. Never controls Chromium or Xorg."""
import base64
import ctypes
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import signal
import socket
import ssl
import subprocess
import sys
import tempfile
import time

STATE = Path('/state/sunshine')
CONF = STATE / 'sunshine.conf'
POLICY = Path('/run/vyos-kiosk-policy/sunshine.json')
SOCKET = '/run/kiosk/sunshine-control.sock'
LIMIT = 16384


def capture_environment(base=None):
    """One rotation authority: native kiosk setting, only for opt-in GPU/RGA."""
    env = dict(os.environ if base is None else base)
    if (env.get('KIOSK_DISPLAY_BACKEND') == 'wayland'
            and env.get('SUNSHINE_VYARM_DIRECT_RGA') == '1'):
        value = env.get('KIOSK_ROTATION', '0')
        if value not in ('0', '90', '180', '270'):
            raise ValueError('Invalid kiosk rotation for Sunshine')
        rotation = int(value)
        env['SUNSHINE_VYARM_KMS_ROTATION'] = str((360 - rotation) % 360)
        env['SUNSHINE_VYARM_ABS_ROTATION'] = str(rotation)
    return env


def atomic(path, text):
    if path.is_symlink():
        raise ValueError('Refusing symlink destination')
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_config():
    text = CONF.read_text() if CONF.exists() else ''
    values = {}
    for line in text.splitlines():
        match = re.match(r'^\s*([a-zA-Z0-9_]+)\s*=\s*(.*?)\s*$', line)
        if match:
            values[match[1]] = match[2]
    return text, values


def owned(policy):
    control = policy['input'] == 'control'
    return {'stream_audio': 'enabled' if policy['audio'] == 'enabled' else 'disabled',
            'keyboard': str(control).lower(), 'mouse': str(control).lower(),
            'native_pen_touch': str(control).lower(), 'controller': 'disabled',
            'lan_encryption_mode': '2', 'wan_encryption_mode': '2', 'upnp': 'disabled',
            'csrf_allowed_origins': ','.join(policy.get('web_origins', []))}


def merge_config(text, settings):
    # Preserve all non-owned lines, including encoder tuning and paths.
    kept = []
    for line in text.splitlines(keepends=True):
        match = re.match(r'^\s*([a-zA-Z0-9_]+)\s*=', line)
        if not match or match[1] not in settings:
            kept.append(line)
    body = ''.join(kept)
    if body and not body.endswith('\n'):
        body += '\n'
    return body + ''.join(f'{key} = {value}\n' for key, value in settings.items())


def read_policy():
    data = json.loads(POLICY.read_text())
    if data.get('version') != 1 or set(data) - {'version', 'access', 'input', 'audio', 'web_origins'} or not {'version','access','input','audio'} <= set(data):
        raise ValueError('Unsupported policy format')
    for key, allowed in {'access': ('enabled', 'disabled'), 'input': ('view-only', 'control'),
                         'audio': ('enabled', 'disabled')}.items():
        if data.get(key) not in allowed:
            raise ValueError('Invalid policy')
    origins=data.get('web_origins',[])
    if not isinstance(origins,list) or len(origins)>16:raise ValueError('Invalid Web origins')
    for origin in origins:
        if not isinstance(origin,str) or not re.fullmatch(r'https://(?:[A-Za-z0-9][A-Za-z0-9.-]*|\[[0-9a-fA-F:]+\])(?::[0-9]{1,5})?',origin):raise ValueError('Invalid Web origin')
        from urllib.parse import urlsplit
        if urlsplit(origin).port == 0:raise ValueError('Invalid Web port')
    return data


def state_path(config, key, default):
    value = Path(config.get(key, default))
    if not value.is_absolute():
        value = STATE / value
    if value.is_symlink() or not value.resolve().is_relative_to(STATE.resolve()):
        raise ValueError('Credential/certificate paths must remain inside persistent Sunshine state')
    return value


def credentials_path(config):
    return state_path(config, 'credentials_file', config.get('file_state', 'sunshine_state.json'))


def credential_update(data, username, password):
    if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,64}', username) or len(password) < 12:
        raise ValueError('Username invalid or password shorter than 12 characters')
    salt = secrets.token_hex(8)
    # Sunshine 63d35f7 crypto::hash + util::hex (default reverse byte order).
    digest = hashlib.sha256((password + salt).encode()).digest()[::-1].hex().upper()
    return dict(data, username=username, salt=salt, password=digest)


def api(config, request, method, path, payload=None):
    port = int(config.get('port', '47989')) + 1
    if not 1 <= port <= 65535:
        raise ValueError('Invalid Sunshine port')
    cert = state_path(config, 'cert', 'credentials/cacert.pem')
    expected = ssl.PEM_cert_to_DER_cert(cert.read_text())
    # Fixed container loopback only, pinned to this instance's persistent cert.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    conn = http.client.HTTPSConnection('127.0.0.1', port, timeout=20, context=context)
    try:
        conn.connect()
        if conn.sock.getpeercert(binary_form=True) != expected:
            raise ValueError('Sunshine certificate differs from persistent certificate')
        user = request.get('username', '')
        password = request.get('password', '')
        auth = base64.b64encode(f'{user}:{password}'.encode()).decode()
        headers = {'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'}
        body = None if payload is None else json.dumps(payload).encode()
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read(1024 * 1024 + 1)
        if response.status != 200:
            raise ValueError(f'Sunshine API returned HTTP {response.status}')
        if len(raw) > 1024 * 1024:
            raise ValueError('Sunshine response too large')
        result = json.loads(raw)
        if result.get('status') is False:
            raise ValueError('Sunshine rejected the requested operation')
        return result
    finally:
        conn.close()


def parent_death_signal():
    # Linux kiosk container: do not leave remote access running if its owner dies.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'Unable to set parent death signal')
    if os.getppid() == 1:
        os.kill(os.getpid(), signal.SIGKILL)


class Supervisor:
    def __init__(self):
        self.proc = None
        self.log = None
        self.policy = None
        self.error = None
        self.retry = 0
        self.starts = 0

    def stop(self):
        if self.proc is not None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
                self.proc.wait(timeout=5)
            except ProcessLookupError:
                pass
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()
            self.proc = None
        if self.log:
            self.log.close()
            self.log = None

    def tick(self):
        try:
            policy = read_policy()
            text, config = read_config()
            settings = owned(policy)
            changed = policy != self.policy or any(config.get(k) != v for k, v in settings.items())
            if changed:
                self.stop()
                merged = merge_config(text, settings)
                if merged != text:
                    if not (STATE / 'sunshine.conf.before-cli').exists():
                        atomic(STATE / 'sunshine.conf.before-cli', text)
                    atomic(CONF, merged)
                self.policy = policy
            if policy['access'] == 'disabled':
                self.stop()
                self.error = None
                return
            cred = json.loads(credentials_path(config).read_text())
            if not all(cred.get(k) for k in ('username', 'password', 'salt')):
                raise ValueError('Initialize Web credentials before enabling access')
            if self.proc and self.proc.poll() is not None:
                self.stop()
                self.retry = time.monotonic() + 5
                self.error = 'Sunshine exited; retrying in five seconds'
            if self.proc is None and time.monotonic() >= self.retry:
                self.log = open(STATE / 'runtime.log', 'w')
                command = ['sunshine', str(CONF)]
                if os.environ.get('SUNSHINE_VYARM_DIRECT_RGA') == '1':
                    csc = Path('/sys/module/rockchip_rga/parameters/experimental_full_csc')
                    if not csc.exists() or csc.read_text().strip() not in ('Y', '1'):
                        raise ValueError('Waiting for host RGA CSC prerequisite')
                    command += ['capture=kms', 'encoder=rkmpp', 'hevc_mode=2']
                self.proc = subprocess.Popen(command, cwd=STATE,
                                             stdout=self.log, stderr=subprocess.STDOUT, env=capture_environment(),
                                             start_new_session=True, preexec_fn=parent_death_signal)
                self.starts += 1
                self.error = None
        except (OSError, ValueError, KeyError) as error:
            self.stop()
            self.error = str(error)

    def handle(self, request):
        action = request.get('action')
        _, config = read_config()
        if action == 'status':
            encoder = []
            log = STATE / 'runtime.log'
            if log.exists():
                with log.open('rb') as f:
                    f.seek(max(0, log.stat().st_size - 65536))
                    encoder = [l for l in f.read().decode(errors='replace').splitlines()
                               if 'encoder' in l.lower() and ('Found' in l or 'Creating' in l)][-8:]
            return {'policy': self.policy, 'running': self.proc is not None and self.proc.poll() is None,
                    'starts': self.starts, 'error': self.error, 'encoder_log': encoder,
                    'note': 'Found = available; Creating = selected. Audio enabled is a request, not proof of a working source.'}
        if action == 'reset-credentials':
            path = credentials_path(config)
            data = json.loads(path.read_text()) if path.exists() else {}
            updated = credential_update(data, request.get('username', ''), request.get('password', ''))
            self.stop()  # avoid racing Sunshine's state writer; pairing/certs preserved
            # Read after stop as Sunshine may have flushed state during shutdown.
            data = json.loads(path.read_text()) if path.exists() else {}
            data.update({k: updated[k] for k in ('username', 'salt', 'password')})
            atomic(path, json.dumps(data, indent=2) + '\n')
            self.retry = 0
            self.tick()
            return {'status': True, 'message': 'Web credentials updated; existing streams were interrupted'}
        if self.proc is None or self.proc.poll() is not None:
            raise ValueError('Sunshine is disabled or not running')
        if action == 'clients':
            result = api(config, request, 'GET', '/api/clients/list')
            return {'clients': [{k: c[k] for k in ('uuid', 'name', 'enabled') if k in c}
                                for c in result.get('named_certs', [])]}
        if action == 'pending':
            return api(config, request, 'GET', '/api/pin')
        if action == 'pair':
            pairing = request.get('pairing_id', '')
            pin = request.get('pin', '')
            name = request.get('name', '')
            if not re.fullmatch(r'[0-9a-fA-F]{32}', pairing) or not re.fullmatch(r'[0-9]{4}', pin):
                raise ValueError('Invalid pairing ID or PIN')
            if not 1 <= len(name.encode()) <= 128:
                raise ValueError('Client name must contain 1 to 128 bytes')
            return api(config, request, 'POST', '/api/pin', {'pairing_id': pairing, 'pin': pin, 'name': name})
        if action == 'revoke':
            uuid = request.get('uuid', '')
            if not re.fullmatch(r'[A-Za-z0-9-]{1,80}', uuid):
                raise ValueError('Invalid client UUID')
            result = api(config, request, 'POST', '/api/clients/unpair', {'uuid': uuid})
            self.stop()  # revoke existing sessions too, not just future pairing auth
            self.retry = 0
            self.tick()
            return result
        raise ValueError('Unsupported action')


def receive(conn):
    raw = bytearray()
    while b'\n' not in raw:
        part = conn.recv(4096)
        if not part:
            raise ValueError('Incomplete request')
        raw.extend(part)
        if len(raw) > LIMIT:
            raise ValueError('Request too large')
    return json.loads(raw.split(b'\n', 1)[0])


def serve():
    STATE.mkdir(parents=True, exist_ok=True)
    running = True
    def stop(_sig, _frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    supervisor = Supervisor()
    with socket.socket(socket.AF_UNIX) as server:
        if os.path.lexists(SOCKET):
            os.unlink(SOCKET)
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o600)
        server.listen(2)
        server.settimeout(.5)
        try:
            while running:
                supervisor.tick()
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                with conn:
                    conn.settimeout(5)
                    try:
                        reply = supervisor.handle(receive(conn))
                    except (OSError, ValueError, KeyError, http.client.HTTPException) as error:
                        reply = {'error': str(error)}
                    try:
                        conn.sendall(json.dumps(reply).encode() + b'\n')
                    except OSError:
                        pass
        finally:
            supervisor.stop()
            os.unlink(SOCKET)


def client():
    raw = sys.stdin.buffer.read(LIMIT + 1)
    if len(raw) > LIMIT:
        raise ValueError('Request too large')
    json.loads(raw)
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(30)
        conn.connect(SOCKET)
        conn.sendall(raw.rstrip(b'\n') + b'\n')
        reply = receive(conn)
    print(json.dumps(reply))
    return 1 if reply.get('error') else 0


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['serve']:
            serve()
        elif sys.argv[1:] == ['request']:
            sys.exit(client())
        else:
            raise ValueError('Use serve or request')
    except (OSError, ValueError) as error:
        print(json.dumps({'error': str(error)}))
        sys.exit(1)
