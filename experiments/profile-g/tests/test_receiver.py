from types import SimpleNamespace
import base64
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/profile-g/cli'),str(ROOT/'experiments/profile-g/container')]
import receiver
import backend

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class Policy(unittest.TestCase):
    def cfg(self,**settings):
        return {'receiver':settings, 'image':'localhost/vyarm-receiver:test',
                'allow_host_networks':{}, 'volume':{'state':{'source':'/config/receiver/state','destination':'/state','mode':'rw'}},
                'device':{'display':{'source':'/dev/dri/card0','destination':'/dev/dri/card0'}}}
    def test_decoder_environment_is_scoped(self):
        inherited={'PULSE_SERVER':'unix:/run/receiver/pulse/native'}
        for method,codec,decoder in itertools.product(('airplay','moonlight'),('auto','h264','hevc','av1'),('auto','hardware','software')):
            cfg=receiver.settings(dict(method=method,codec=codec,decoder=decoder,host='host'))
            env=backend.receiver_environment(cfg,inherited)
            selected=method=='moonlight' and codec=='h264' and decoder!='software'
            self.assertEqual('LD_LIBRARY_PATH' in env,selected)
            self.assertEqual(env['PULSE_SERVER'],inherited['PULSE_SERVER'])
        for codec,decoder in itertools.product(('auto','h264','hevc','av1'),('auto','hardware','software')):
            pair=receiver.settings(dict(method='moonlight',mode='pair',codec=codec,decoder=decoder))
            env=backend.receiver_environment(pair,inherited)
            self.assertEqual('LD_LIBRARY_PATH' in env,decoder!='software')
            if decoder!='software':
                self.assertEqual(env['LD_LIBRARY_PATH'],'/opt/ffmpeg-request/lib')
                self.assertEqual(env['DRM_FORCE_EGL'],'1')
        self.assertEqual(inherited,{'PULSE_SERVER':'unix:/run/receiver/pulse/native'})

    def test_non_receiver_unchanged(self):
        self.assertEqual(receiver.environment({'kiosk':{'url':'https://example.org'}}),[])
    def test_roundtrip_and_defaults(self):
        cfg=self.cfg(); line=receiver.environment(cfg)[0]
        encoded=line.split('"')[1]
        values=json.loads(base64.b64decode(encoded))
        self.assertEqual(values['decoder'],'auto');self.assertEqual(values['method'],'airplay')
    def test_invalid_values(self):
        for key,value in [('method','cast'),('name','x\nAddCapability=ALL'),('fps','0'),('fps','121'),
                          ('drm_device','../card0'),('wifi_interface','wlan0;reboot'),('resolution','9000x9000'),
                          ('latency','-1'),('codec','raw'),('app','--help')]:
            with self.subTest(key=key), self.assertRaises(ValueError): receiver.settings({key:value})
    def test_requirements(self):
        for key in ('allow_host_networks','volume','device'):
            cfg=self.cfg();del cfg[key]
            with self.subTest(key=key),self.assertRaises(ValueError):receiver.environment(cfg)
    def test_refuses_conflicting_configuration(self):
        for extra in ({'kiosk':{}},{'network':{'bridge':{}}},{'command':'sh'},
                      {'environment':{'G_RECEIVER_CONFIG':{'value':'override'}}}):
            cfg=self.cfg();cfg.update(extra)
            with self.assertRaises(ValueError):receiver.environment(cfg)
    def test_state_cannot_escape_config(self):
        cfg=self.cfg();cfg['volume']['state']['source']='/config/../../etc'
        with self.assertRaises(ValueError):receiver.environment(cfg)
    def test_moonlight_pair_and_stream(self):
        with self.assertRaises(ValueError):receiver.settings({'method':'moonlight'})
        self.assertEqual(receiver.settings({'method':'moonlight','mode':'pair'})['mode'],'pair')
        with self.assertRaises(ValueError):receiver.settings({'method':'airplay','mode':'pair'})
        cmd=backend.command(receiver.settings({'method':'moonlight','host':'192.168.1.5','app':'Desktop screen','codec':'hevc'}))
        self.assertEqual(cmd[1:4],['stream','192.168.1.5','Desktop screen'])
        self.assertIn('HEVC',cmd);self.assertIn('never',cmd)
    def test_hardware_is_not_silently_software(self):
        with self.assertRaises(ValueError):backend.gst_decoder('hardware',lambda _:False)
        self.assertEqual(backend.gst_decoder('hardware',lambda n:n=='v4l2slh264dec'),'v4l2slh264dec')
        self.assertEqual(backend.gst_decoder('software'),'avdec_h264')
    def test_airplay_pairing_is_persistent(self):
        with patch.object(backend,'gst_decoder',return_value='decodebin'):
            cmd=backend.command(receiver.settings({}))
        self.assertIn('-pin',cmd);self.assertIn('/state/airplay-key',cmd);self.assertIn('/state/airplay-clients',cmd)
    def test_miracast_requires_interface_and_capability(self):
        with self.assertRaises(ValueError):receiver.settings({'method':'miracast'})
        cfg=self.cfg(method='miracast',wifi_interface='wlan1')
        with self.assertRaises(ValueError):receiver.environment(cfg)
        cfg['capability']=['net-admin']
        with self.assertRaisesRegex(ValueError,'net-raw'):receiver.environment(cfg)
        cfg['capability']=['net-admin','net-raw'];self.assertTrue(receiver.environment(cfg))
    def test_display_conflict_and_disabled_kiosk(self):
        g=self.cfg(); f={'kiosk':{},'device':copy.deepcopy(g['device'])}
        with self.assertRaisesRegex(ValueError,'shared'):receiver.verify_all({'name':{'g':g,'f':f}},image_probe=lambda _:None)
        f['disable']={};receiver.verify_all({'name':{'g':g,'f':f}},image_probe=lambda _:None)
    def test_wireless_candidate_config_is_protected(self):
        g=self.cfg(method='miracast',wifi_interface='wlan1');g['capability']=['net-admin','net-raw']
        probe=lambda _: {'siblings':['wlan1','ap1']}
        with self.assertRaisesRegex(ValueError,'interfaces wireless'):
            receiver.verify_all({'name':{'g':g}},{'wireless':{'ap1':{}}},probe=probe,image_probe=lambda _:None)
    def test_only_compatible_local_image(self):
        with patch.object(receiver,'read_command',return_value='[{"Config":{"Labels":{}}}]'),self.assertRaises(ValueError):
            receiver.verify_image('image')
    def test_repeated_generation_does_not_mutate_config(self):
        cfg=self.cfg();before=copy.deepcopy(cfg)
        self.assertEqual(receiver.environment(cfg),receiver.environment(cfg));self.assertEqual(cfg,before)

class Wireless(unittest.TestCase):
    def check(self, modes='P2P-client\n * P2P-GO', state=None, detail='type managed', sibling=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);sysnet=root/'net';sysnet.mkdir();phy=root/'phy0';phy.mkdir()
            for name in (['wlan1','ap1'] if sibling else ['wlan1']):
                (sysnet/name).mkdir();(sysnet/name/'phy80211').symlink_to(phy)
            def run(*args):
                if args[:2]==('iw','phy'):return 'Supported interface modes:\n * '+modes+'\nBand 1:\n'
                if args[0]=='ip':return json.dumps([state or {'flags':['BROADCAST'],'addr_info':[]}])
                return detail
            return receiver.wifi_report('wlan1',sysnet,run)
    def test_p2p_is_capability_not_stream_acceptance(self):
        result=self.check();self.assertTrue(result['p2p_advertised']);self.assertFalse(result['miracast_tested'])
    def test_missing_modes_rejected(self):
        with self.assertRaisesRegex(ValueError,'advertise'):self.check(modes='managed\n * AP')
    def test_up_address_and_ap_rejected(self):
        for state in ({'flags':['UP']},{'addr_info':[{'local':'10.0.0.1'}]},{'master':'br0'}):
            with self.assertRaisesRegex(ValueError,'in use'):self.check(state=state)
        with self.assertRaisesRegex(ValueError,'in use'):self.check(detail='type AP',sibling=True)

class Source(unittest.TestCase):
    def test_prepare_is_additive_and_refuses_drift(self):
        prep=load('g_prepare','experiments/profile-g/cli/prepare-source.py')
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('src/conf_mode','interface-definitions','python/vyos'):(root/name).mkdir(parents=True)
            owner=root/'src/conf_mode/container.py'
            owner.write_text("from vyos import ConfigError\ndef get_config(config=None):\n    conf = config\n    container = conf.get_config_dict(['container'])\n    return container\ndef verify(container):\n    # Add new container\n    pass\ndef generate(container_config):\n    out = []\n    if 'health_check' in container_config:\n        pass\n    return out\n")
            schema=root/'interface-definitions/container.xml.in'
            schema.write_text('<interfaceDefinition><node name="container"><children>\n          <leafNode name="allow-host-pid"><properties><help>existing</help></properties></leafNode>\n</children></node></interfaceDefinition>')
            prep.prepare(root)
            self.assertIn('allow-host-pid',schema.read_text());self.assertIn('receiver',schema.read_text())
            compile(owner.read_text(),str(owner),'exec')
            # Config collection must use the supplied transaction, never reread
            # global Config in verify (required by VyOS configd).
            import ast
            tree=ast.parse(owner.read_text())
            nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
            namespace={'receiver':SimpleNamespace(verify_all=lambda c,i: seen.append(i)),
                       'ConfigError':ValueError,'subprocess':__import__('subprocess')}
            exec(compile(ast.Module(body=nodes,type_ignores=[]),'<prepared>','exec'),namespace)
            interfaces={'wireless':{'wlan0':{'type':'access-point'}}}
            for enabled in (False,True):
                calls=[];seen=[]
                cfg={'name':{'test':{'receiver':{}}}} if enabled else {}
                def get_config_dict(path,**kwargs):
                    calls.append(path)
                    return cfg if path==['container'] else interfaces
                result=namespace['get_config'](SimpleNamespace(get_config_dict=get_config_dict))
                namespace['verify'](result)
                self.assertEqual(calls,[['container'],['interfaces']] if enabled else [['container']])
                self.assertEqual(seen,[interfaces if enabled else {}])
            with self.assertRaises(ValueError):prep.prepare(root)
    def test_existing_profile_combinations_unchanged(self):
        feature=load('feature','tools/feature-profile.py')
        for flags in itertools.product((False,True),repeat=4):
            baseline=feature.derive(*flags)
            self.assertNotIn('receiver_g',baseline['features'])
            new=feature.derive(*flags,True)
            self.assertEqual(new['enabled_features'],baseline['enabled_features']+['receiver-g'])
            self.assertTrue(new['profile'].endswith('receiver'))

if __name__=='__main__':unittest.main()
