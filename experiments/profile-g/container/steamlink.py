#!/usr/bin/env python3
"""Pinned Steam client adapter. State is persistent; libraries remain private."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

SHELL_SHA256 = 'b245adfccc2cda43e405194cd66615c30ffdae6f7416b7db0579d5c161a3f7fd'
RUNTIME = Path('/opt/steamlink')
REQUEST = Path('/opt/ffmpeg-request')

def varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128); value >>= 7
    out.append(value)
    return bytes(out)

def read_varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data): raise ValueError('Truncated Steam settings')
        b = data[pos]; pos += 1; value |= (b & 127) << shift
        if b < 128: return value, pos
    raise ValueError('Invalid Steam settings varint')

def update_protobuf(data, values):
    """Preserve unknown Valve fields, including nested messages, byte for byte."""
    if len(data) > 1024*1024: raise ValueError('Oversized Steam settings')
    pos = 0; kept = []
    while pos < len(data):
        start = pos; tag, pos = read_varint(data, pos); field, wire = tag >> 3, tag & 7
        if not field: raise ValueError('Invalid Steam field')
        if wire == 0: _, pos = read_varint(data, pos)
        elif wire == 1: pos += 8
        elif wire == 2:
            size, pos = read_varint(data, pos); pos += size
        elif wire == 5: pos += 4
        else: raise ValueError('Unsupported Steam wire type')
        if pos > len(data): raise ValueError('Truncated Steam field')
        if field not in values: kept.append(data[start:pos])
    return b''.join(kept) + b''.join(varint(k << 3) + varint(v) for k,v in sorted(values.items()))

def configure(path, cfg, hardware):
    w,h = map(int,cfg['resolution'].split('x'))
    values = {2:w,3:h,4:int(cfg['fps']),5:1,6:int(cfg['bitrate']),7:int(hardware),
              13:int(hardware and cfg['codec']=='hevc'),26:0}
    path.parent.mkdir(parents=True,exist_ok=True)
    old = path.read_bytes() if path.exists() else b''
    new = update_protobuf(old,values)  # Validate before creating backup or changing state.
    backup = path.with_suffix('.bin.before-profile-g')
    if old and not backup.exists():
        with backup.open('xb') as f: f.write(old)
        backup.chmod(0o600)
    tmp = path.with_suffix('.tmp')
    with tmp.open('wb') as f:
        os.fchmod(f.fileno(),0o600); f.write(new); f.flush(); os.fsync(f.fileno())
    tmp.replace(path)

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def check_runtime(runtime=RUNTIME, root=Path('/')):
    if digest(runtime/'bin/shell') != SHELL_SHA256:
        raise ValueError('Unsupported Steam executable; pinned version required')
    entries = (runtime/'request-libs.sha256').read_text().splitlines()
    if not entries: raise ValueError('Missing private decoder manifest')
    checked = set()
    for entry in entries:
        expected, name = entry.split(maxsplit=1)
        if not name.startswith('opt/ffmpeg-request/lib/') or '..' in Path(name).parts:
            raise ValueError('Invalid private decoder manifest')
        if digest(root/name) != expected: raise ValueError('Private decoder checksum mismatch: '+name)
        checked.add(Path(name).name.split('.so')[0])
    if not {'libavcodec','libavutil'}.issubset(checked): raise ValueError('Incomplete decoder manifest')

def hardware_available(codec, dev=Path('/dev'), sysvideo=Path('/sys/class/video4linux')):
    # Require actual grants, not only host sysfs (which is visible inside containers).
    names=[]
    for node in sysvideo.glob('video*'):
        if (dev/node.name).is_char_device(): names.append((node/'name').read_text().lower())
    return (any((dev/'dri').glob('renderD*')) and any(dev.glob('media*'))
            and (any('rkvdec' in n for n in names) if codec == 'hevc' else
                 any('hantro' in n or 'rk3568-vpu-dec' in n for n in names)))

def private_heap(uid, gid, source=Path('/dev/dma_heap/system'), target=Path('/dev/dma_heap/vidbuf_cached')):
    """Create only a container-private alias; never chmod the host device bind."""
    node = source.stat()
    if not stat.S_ISCHR(node.st_mode): raise ValueError('Explicit system DMA heap grant required')
    if target.exists(): raise ValueError('Private DMA heap alias already exists; do not bind host aliases')
    os.mknod(target,stat.S_IFCHR | 0o600,node.st_rdev)
    os.chown(target,uid,gid)

def launch_environment(cfg, inherited=None):
    env = dict(os.environ if inherited is None else inherited)
    # Reject an unreviewed executable even for software mode: network guard is pinned too.
    if digest(RUNTIME/'bin/shell') != SHELL_SHA256: raise ValueError('Unsupported Steam executable')
    hardware = False; reason = None
    if cfg['decoder'] != 'software':
        try:
            check_runtime()
            if not hardware_available(cfg['codec']): raise ValueError('Hantro/rkvdec device grants unavailable')
            util=ctypes.CDLL(str(REQUEST/'lib/libavutil.so.59'))
            util.av_hwdevice_find_type_by_name.argtypes=[ctypes.c_char_p]
            if util.av_hwdevice_find_type_by_name(b'v4l2request') != 13:
                raise ValueError('Unexpected private FFmpeg ABI')
            hardware=True
        except (OSError,ValueError) as exc:
            if cfg['decoder']=='hardware': raise ValueError('Hardware decoder refused: '+str(exc)) from exc
            reason=str(exc)
    state=Path(env['HOME'])/'.local/share/Valve Corporation/SteamLink'
    configure(state/'streaming_settings.bin',cfg,hardware)
    temp=Path(env['XDG_RUNTIME_DIR'])/'steamlink-tmp';temp.mkdir(mode=0o700,exist_ok=True)
    qt=RUNTIME/'Qt-5.14.1'
    libs=[str(RUNTIME/'lib'),str(qt/'lib')]
    preload=[str(RUNTIME/'ifaddrs-guard.so')]
    if hardware:
        libs.insert(0,str(REQUEST/'lib'));preload.insert(0,str(RUNTIME/'request-bridge.so'))
    env.pop('G_STEAMLINK_HEVC',None)
    if hardware and cfg['codec']=='hevc': env['G_STEAMLINK_HEVC']='1'
    env.update(LD_LIBRARY_PATH=':'.join(libs),LD_PRELOAD=':'.join(preload),
               TMPDIR=str(temp),SDL_GAMECONTROLLERCONFIG_FILE=str(state/'controller_map.txt'),
               SDL_AUDIODRIVER='pulseaudio',QT_QPA_PLATFORM='xcb',SDL_VIDEODRIVER='wayland',
               QT_PLUGIN_PATH=str(qt/'plugins'),QTDIR=str(qt),PATH=str(RUNTIME/'bin')+':'+env['PATH'])
    status={'method':'steamlink','decoder_requested':cfg['decoder'],
            'decoder_selected':'v4l2request' if hardware else 'software',
            'codec_selected':'hevc' if hardware and cfg['codec']=='hevc' else 'h264',
            'fallback_reason':reason,'stream_verified':False}
    (Path(env['HOME'])/'steamlink-runtime.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status),flush=True)
    return env

if __name__=='__main__':
    from backend import config
    env=launch_environment(config())
    os.chdir(RUNTIME)
    os.execve(RUNTIME/'bin/shell',[str(RUNTIME/'bin/shell')],env)
