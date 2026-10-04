import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

BASE = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
remote = load('remote', BASE/'cli/remote.py')
runtime = load('runtime', BASE/'container/kiosk-sunshine.py')

class PolicyTest(unittest.TestCase):
    def test_defaults_and_explicit_off(self):
        self.assertEqual(remote.policy({'kiosk': {}}), {'version': 1, 'access': 'disabled', 'input': 'view-only', 'audio': 'disabled'})
        cfg = {'kiosk': {'remote': {'audio': 'enabled', 'access': 'enabled'}}}
        self.assertEqual(remote.policy(cfg)['audio'], 'enabled')
        cfg['kiosk']['remote']['audio'] = 'disabled'
        self.assertEqual(remote.policy(cfg)['audio'], 'disabled')
        cfg['kiosk']['remote']['audio'] = 'yes'
        with self.assertRaises(ValueError): remote.policy(cfg)
    def test_remote_change_only(self):
        a = {'kiosk': {'url': 'https://example.org', 'rotation': '90'}, 'image': 'one'}
        b = copy.deepcopy(a); b['kiosk']['remote'] = {'audio': 'enabled'}
        self.assertTrue(remote.remote_only(a,b))
        self.assertFalse(remote.remote_only(a,a))
        b['kiosk']['rotation']='0'; self.assertFalse(remote.remote_only(a,b))
        self.assertFalse(remote.remote_only({},b))
    def test_mount_must_be_correct_and_readonly(self):
        m={'Source':str(remote.directory('test')), 'Destination':remote.DEST, 'RW':False}
        with patch.object(remote.subprocess,'run') as run:
            run.return_value.stdout=json.dumps([{'State':{'Running':True}, 'Mounts':[m]}])
            self.assertTrue(remote.mounted_policy('test'))
            m['RW']=True
            run.return_value.stdout=json.dumps([{'State':{'Running':True}, 'Mounts':[m]}])
            self.assertFalse(remote.mounted_policy('test'))
    def test_policy_atomic_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(remote,'ROOT',Path(tmp)):
            cfg={'kiosk': {'remote': {'audio':'disabled'}}}
            remote.write_policy('kiosk',cfg)
            p=Path(tmp)/'kiosk/sunshine.json'; old=p.stat().st_ino
            remote.write_policy('kiosk',cfg); self.assertEqual(p.stat().st_ino,old)
            cfg['kiosk']['remote']['audio']='enabled';remote.write_policy('kiosk',cfg)
            self.assertEqual(json.loads(p.read_text())['audio'],'enabled')
            self.assertEqual(p.stat().st_mode & 0o777,0o644)
    def test_incompatible_image_rejected(self):
        with patch.object(remote.subprocess,'run') as run:
            run.return_value.stdout='[{"Labels":{}}]'
            with self.assertRaises(ValueError): remote.verify_image({'image':'old','kiosk':{'remote':{}}})
            remote.verify_image({'image':'old','kiosk':{'url':'file:///a'}})

class RuntimeTest(unittest.TestCase):
    def test_capture_rotation_is_derived_only_for_opt_in_wayland(self):
        original = {'KIOSK_DISPLAY_BACKEND':'wayland', 'KIOSK_ROTATION':'90',
                    'SUNSHINE_VYARM_DIRECT_RGA':'1'}
        derived = runtime.capture_environment(original)
        self.assertEqual(derived['SUNSHINE_VYARM_KMS_ROTATION'], '270')
        self.assertEqual(derived['SUNSHINE_VYARM_ABS_ROTATION'], '90')
        self.assertNotIn('SUNSHINE_VYARM_KMS_ROTATION', original)
        for base in (dict(original, KIOSK_DISPLAY_BACKEND='x11'),
                     dict(original, SUNSHINE_VYARM_DIRECT_RGA='0')):
            self.assertEqual(runtime.capture_environment(base), base)
        with self.assertRaises(ValueError):
            runtime.capture_environment(dict(original, KIOSK_ROTATION='invalid'))

    def test_managed_keys_preserve_web_settings(self):
        text='# encoder tuning\nencoder = rkmpp\nstream_audio = enabled\nstream_audio = disabled\naudio_sink = custom\n'
        policy=remote.policy({'kiosk':{'remote':{'audio':'enabled'}}})
        result=runtime.merge_config(text,runtime.owned(policy))
        self.assertIn('encoder = rkmpp\n',result);self.assertIn('audio_sink = custom\n',result)
        self.assertEqual(result.count('stream_audio ='),1)
        self.assertIn('stream_audio = enabled',result)
        self.assertEqual(runtime.merge_config(result,runtime.owned(policy)),result)
        self.assertIn('lan_encryption_mode = 2',result)
    def test_view_only_disables_all_remote_input(self):
        settings=runtime.owned(remote.policy({}))
        self.assertEqual([settings[k] for k in ('keyboard','mouse','native_pen_touch')],['false']*3)
        self.assertEqual(settings['controller'],'disabled')
    def test_credentials_preserve_pairings(self):
        state={'root':{'named_devices':[{'uuid':'test'}]},'username':'old'}
        result=runtime.credential_update(state,'new','a-long-test-password')
        self.assertEqual(result['root'],state['root']);self.assertEqual(state['username'],'old')
        self.assertEqual(len(result['password']),64)
        with self.assertRaises(ValueError): runtime.credential_update(state,'new','short')
    def test_path_escape_rejected(self):
        with self.assertRaises(ValueError): runtime.credentials_path({'credentials_file':'/etc/passwd'})
        with self.assertRaises(ValueError): runtime.credentials_path({'credentials_file':'../outside'})
    def test_fail_closed_missing_policy(self):
        s=runtime.Supervisor()
        with patch.object(runtime,'read_policy',side_effect=FileNotFoundError('missing')), patch.object(s,'stop') as stop:
            s.tick();stop.assert_called_once();self.assertIsNotNone(s.error)
    def test_disable_stops_only_owned_sunshine(self):
        s=runtime.Supervisor(); p=remote.policy({})
        with patch.object(runtime,'read_policy',return_value=p), patch.object(runtime,'read_config',return_value=('',{})), patch.object(runtime,'atomic'), patch.object(s,'stop') as stop:
            s.tick();self.assertTrue(stop.called);self.assertIsNone(s.proc)
    def test_no_restart_for_unchanged_config(self):
        s=runtime.Supervisor();p=remote.policy({'kiosk':{'remote':{'access':'enabled'}}})
        s.policy=p;s.proc=Mock();s.proc.poll.return_value=None
        with tempfile.TemporaryDirectory() as tmp:
            creds=Path(tmp)/'state.json';creds.write_text('{"username":"a","salt":"b","password":"c"}')
            with patch.object(runtime,'read_policy',return_value=p), patch.object(runtime,'read_config',return_value=('',runtime.owned(p))), patch.object(runtime,'credentials_path',return_value=creds), patch.object(s,'stop') as stop:
                s.tick();stop.assert_not_called()
    def test_audio_change_restarts_sunshine_and_preserves_config(self):
        s=runtime.Supervisor(); old=remote.policy({});s.policy=old
        new=remote.policy({'kiosk':{'remote':{'audio':'enabled'}}})
        with patch.object(runtime,'read_policy',return_value=new),patch.object(runtime,'read_config',return_value=('encoder = rkmpp\n',runtime.owned(old))),patch.object(runtime,'atomic') as write,patch.object(s,'stop') as stop:
            s.tick();self.assertTrue(stop.called)
            merged=[c.args[1] for c in write.call_args_list if c.args[0]==runtime.CONF][0]
            self.assertIn('encoder = rkmpp',merged);self.assertIn('stream_audio = enabled',merged)

if __name__=='__main__': unittest.main()

class ProcessIntegrationTest(unittest.TestCase):
    def test_policy_switch_keeps_desktop_and_credentials(self):
        import os
        import socket
        import subprocess
        import sys
        import time
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'state';state.mkdir();binpath=root/'bin';binpath.mkdir()
            fake=binpath/'sunshine';fake.write_text('#!/usr/bin/env python3\nimport time\nwhile True: time.sleep(.1)\n');fake.chmod(0o755)
            conf=state/'sunshine.conf';conf.write_text('encoder = custom\naudio_sink = preserve-me\n')
            creds=state/'sunshine_state.json';creds.write_text('{"username":"old","password":"hash","salt":"salt","root":{"paired":"keep"}}')
            policy=root/'sunshine.json';policy.write_text(json.dumps(remote.policy({'kiosk':{'remote':{'access':'enabled'}}})))
            sock=str(root/'control.sock')
            code=f'import importlib.util; from pathlib import Path; s=importlib.util.spec_from_file_location("remote",{str(BASE/"container/kiosk-sunshine.py")!r}); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.STATE=Path({str(state)!r}); m.CONF=Path({str(conf)!r}); m.POLICY=Path({str(policy)!r}); m.SOCKET={sock!r}; m.serve()'
            env=dict(os.environ,PATH=str(binpath)+':'+os.environ['PATH'])
            supervisor=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            desktop=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
            def request(data):
                with socket.socket(socket.AF_UNIX) as conn:
                    conn.settimeout(6);conn.connect(sock);conn.sendall(json.dumps(data).encode()+b'\n');return runtime.receive(conn)
            def wait_for(predicate):
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    try:
                        status=request({'action':'status'})
                        if predicate(status):return status
                    except (OSError,ValueError):pass
                    time.sleep(.15)
                self.fail('Supervisor did not reach expected state')
            try:
                first=wait_for(lambda s:s['running'])
                p=remote.policy({'kiosk':{'remote':{'access':'disabled'}}});policy.write_text(json.dumps(p))
                wait_for(lambda s:not s['running'] and s['policy']['access']=='disabled')
                self.assertIsNone(desktop.poll())
                p.update(access='enabled',audio='enabled',input='control');policy.write_text(json.dumps(p))
                current=wait_for(lambda s:s['running'] and s['policy']['audio']=='enabled')
                self.assertGreater(current['starts'],first['starts']);self.assertIsNone(desktop.poll())
                self.assertIn('audio_sink = preserve-me',conf.read_text());self.assertIn('stream_audio = enabled',conf.read_text())
                response=request({'action':'reset-credentials','username':'new','password':'a-strong-new-test-password'})
                self.assertTrue(response['status']);self.assertEqual(json.loads(creds.read_text())['root'],{'paired':'keep'})
                self.assertIsNone(desktop.poll())
                policy.unlink();wait_for(lambda s:not s['running'] and s['error'] is not None)
                self.assertIsNone(desktop.poll())
            finally:
                supervisor.terminate();supervisor.wait(timeout=10)
                desktop.terminate();desktop.wait(timeout=3)

class NativeWaylandTransitionTest(unittest.TestCase):
    def test_device_access_requires_recreation_audio_does_not(self):
        a = {'kiosk': {'display_backend': 'wayland', 'remote': {'access': 'disabled'}}}
        b = copy.deepcopy(a); b['kiosk']['remote'].update(access='enabled', input='control')
        self.assertFalse(remote.remote_only(a, b))
        c = copy.deepcopy(b); c['kiosk']['remote']['audio'] = 'enabled'
        self.assertTrue(remote.remote_only(b, c))
        c['kiosk']['remote']['input'] = 'view-only'
        self.assertFalse(remote.remote_only(b, c))

class OriginPolicyTest(unittest.TestCase):
    def test_roundtrip_and_removal(self):
        cfg={'kiosk':{'remote':{'web_origin':['https://router.example:47990','https://192.168.1.2:47990']}}}
        policy=remote.policy(cfg)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'policy';path.write_text(json.dumps(policy))
            with patch.object(runtime,'POLICY',path):
                self.assertEqual(runtime.read_policy(),policy)
        merged=runtime.merge_config('encoder = rkmpp\ncsrf_allowed_origins = https://old\n',runtime.owned(policy))
        self.assertIn('https://router.example:47990',merged)
        self.assertNotIn('https://old',merged)
        self.assertIn('encoder = rkmpp',merged)
        self.assertEqual(runtime.owned(remote.policy({'kiosk':{}}))['csrf_allowed_origins'],'')
    def test_reject_unsafe_origins(self):
        for origin in ['http://router:47990','https://*.example','https://router/path','https://user:pass@router','https://router:99999','https://router\nupnp = enabled']:
            with self.assertRaises(ValueError):remote.policy({'kiosk':{'remote':{'web_origin':[origin]}}})
