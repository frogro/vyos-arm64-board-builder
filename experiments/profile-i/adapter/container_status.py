"""Read fixed kiosk status files without starting processes inside the container."""
import json
import os
import stat
import subprocess

FILES = {'display': 'display.json', 'media_policy': 'media-status.json',
         'display_schedule': 'schedule.json'}
LIMIT = 262144

def inspect():
    result = subprocess.run(['podman', 'inspect', os.environ.get('VYARM_I_KIOSK','signage-i')],
                            capture_output=True, text=True, timeout=8, check=True)
    return json.loads(result.stdout)[0]

def identity(pid):
    # Field 22, accounting for spaces and parentheses in process comm.
    value = open(f'/proc/{pid}/stat').read()
    return value[value.rfind(')') + 2:].split()[19]

def read_file(directory, name):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMIT:
            raise ValueError('Status file must be a bounded regular file')
        with os.fdopen(fd, 'rb', closefd=False) as source:
            data = source.read(LIMIT + 1)
        if len(data) > LIMIT:
            raise ValueError('Status file exceeds limit')
        result = json.loads(data)
        if not isinstance(result, dict):
            raise ValueError('Status must be a JSON object')
        return result
    finally:
        os.close(fd)

def snapshot():
    result = {}
    container = {}
    fds = []
    try:
        container = inspect()
        state = container['State']
        pid = state['Pid']
        if not state.get('Running') or not isinstance(pid, int) or pid <= 1:
            raise ValueError('Kiosk container is not running')
        started = identity(pid)
        root = os.open(f'/proc/{pid}/root', os.O_RDONLY | os.O_DIRECTORY)
        fds.append(root)
        for component in ('run', 'kiosk'):
            root = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            fds.append(root)
        for key, name in FILES.items():
            try:
                result[key] = read_file(root, name)
            except (OSError, ValueError) as error:
                result[key] = {'unavailable': str(error)}
        after = inspect()
        if (after['Id'] != container['Id'] or not after['State'].get('Running')
                or after['State']['Pid'] != pid or identity(pid) != started):
            raise ValueError('Kiosk restarted while reading status; retry next cycle')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        result = {key: {'unavailable': str(error)} for key in FILES}
    finally:
        for fd in reversed(fds):
            os.close(fd)
    env = container.get('Config', {}).get('Env', [])
    result['configuration'] = dict(item.split('=', 1) for item in env
        if item.startswith(('KIOSK_DISPLAY_', 'KIOSK_AUDIO_MUTED=', 'KIOSK_OUTPUT=',
                            'KIOSK_ROTATION=', 'KIOSK_VIDEO_DECODE=')))
    result['state'] = container.get('State', {'Status': 'unavailable'})
    return result
