#!/usr/bin/env python3
"""Execute real shell functions against hardware/service substitutes; no modem resets."""
from pathlib import Path
import re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'tools/common-firstboot/modem-connect.sh').read_text()
LIB=(ROOT/'tools/common-firstboot/modem-services.sh').read_text()
def function(name):
    return re.search(r'^'+name+r'\(\) \{\n.*?^\}', SRC, re.M|re.S).group()
def run(code):
    return subprocess.run(['bash','-c',code],text=True,capture_output=True,check=True).stdout
class Lifecycle(unittest.TestCase):
    def test_successful_unlock_queues_dependent_without_ordering_deadlock(self):
        with tempfile.TemporaryDirectory() as d:
            unit=Path(d)/'unlock.service'
            config=Path(d)/'modem.conf'
            config.write_text('UNLOCK_KIND=fm350-fcc\n')
            code=f'CONFIG_FILE="{config}"; UNLOCK_SERVICE_PATH="{unit}"; SELF_PATH=/test/modem-connect.sh\n'
            run(code+LIB+'\nwrite_unlock_service_unit')
            self.assertIn('ExecStartPost=/usr/bin/systemctl --no-block start modem-connect.service', unit.read_text())
            self.assertIn('Before=modem-connect.service', unit.read_text())
            config.write_text('UNLOCK_KIND=none\n')
            run(code+'systemctl() { :; }\n'+LIB+'\nwrite_unlock_service_unit')
            self.assertFalse(unit.exists())

    def test_default_route_recovery_respects_native_failover(self):
        with tempfile.TemporaryDirectory() as d:
            wrapper=Path(d)/'op'
            fn=function('restore_wired_default_route').replace('/opt/vyatta/bin/vyatta-op-cmd-wrapper',str(wrapper))
            code='WIRED_WAN=eth7\nlog() { :; }; warn() { :; }; ip() { echo UNEXPECTED_ROUTE_ACCESS; }\n'+fn+'\nrestore_wired_default_route'
            for body in ["echo 'set protocols failover route 0.0.0.0/0 dhcp-interface eth7 metric 10'", "exit 1"]:
                wrapper.write_text('#!/bin/sh\n'+body+'\n');wrapper.chmod(0o755)
                self.assertEqual(run(code),'')
            wrapper.write_text('#!/bin/sh\nexit 0\n')
            self.assertIn('UNEXPECTED_ROUTE_ACCESS',run(code.replace('>/dev/null 2>&1 || return 0','|| return 0',1)))

    def test_boot_waits_for_mount_and_completed_vyos_init(self):
        code = """n=0
mountpoint() { [ "$n" -ge 1 ]; }
systemctl() { if [ "$n" -ge 2 ]; then echo exited; else echo running; fi; }
sleep() { n=$((n+1)); }
"""+function('wait_for_vyos_config')+'\nwait_for_vyos_config; echo "$n"'
        self.assertEqual(run(code).strip(),'2')
    def test_manual_reset_archives_only_modem_settings(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            keys=['CONFIG_FILE','APN_CACHE','MUX_CACHE','BACKEND_CACHE','ROUTE_CACHE',
                  'SERVICE_PATH','UNLOCK_SERVICE_PATH','FAILOVER_SERVICE_PATH',
                  'FAILOVER_SCRIPT_PATH','FM350_RECOVERY_SERVICE_PATH',
                  'FM350_RECOVERY_TIMER_PATH','FM350_UDEV_RULE','FM350_MM_IGNORE_RULE','FM350_LINK_FILE']
            for key in keys: (root/key).write_text('old')
            (root/'unrelated').write_text('keep')
            code=f'PERSIST_DIR="{d}"\n'+ '\n'.join(f'{key}="{root/key}"' for key in keys)
            code+='\nconfig_get() { :; }; systemctl() { :; }; udevadm() { :; }; stop_native_sessions() { :; }; log() { :; }; die() { exit 1; }\n'
            code+=function('reset_manual_modem_setup').replace('/etc/',d+'/etc/')+'\nreset_manual_modem_setup'
            run(code)
            self.assertFalse((root/'CONFIG_FILE').exists())
            self.assertTrue(list(root.glob('previous-*/CONFIG_FILE')))
            self.assertEqual((root/'ROUTE_CACHE').read_text(),'old')
            self.assertEqual((root/'unrelated').read_text(),'keep')
            self.assertFalse((root/'SERVICE_PATH').exists())
    def test_mhi_discovery_recovery_is_scoped_and_bounded(self):
        with tempfile.TemporaryDirectory() as d:
            driver=Path(d)/'sys/bus/pci/drivers/mhi-pci-generic'
            driver.mkdir(parents=True)
            dev=driver/'0000:01:00.0';dev.mkdir()
            (dev/'vendor').write_text('0x17cb');(dev/'device').write_text('0x0306')
            (driver/'unbind').write_text('');(driver/'bind').write_text('')
            code='AUTO_REPAIR=1; TRANSPORT_MODE=pcie; FM350_AVAILABLE=0\n'
            code+='mmcli() { :; }; systemctl() { :; }; sleep() { :; }; udevadm() { :; }; warn() { :; }\n'
            code+=function('recover_undetected_mhi_once').replace('/sys/',d+'/sys/')
            run(code+'\nrecover_undetected_mhi_once || exit 2; if recover_undetected_mhi_once; then exit 3; fi')
            self.assertEqual((driver/'bind').read_text(),'0000:01:00.0')
            (driver/'bind').write_text('')
            run(code+'\nTRANSPORT_MODE=usb; if recover_undetected_mhi_once; then exit 2; fi')
            self.assertEqual((driver/'bind').read_text(),'')

    def test_transport_usb_pcie_and_auto(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for path,values in [('bus/usb/devices/2-1',{'idVendor':'0e8d','idProduct':'7127'}),('bus/pci/devices/0000:01:00.0',{'vendor':'0x14c3','device':'0x4d75'})]:
                p=root/path;p.mkdir(parents=True)
                for key,value in values.items(): (p/key).write_text(value)
            fn=function('detect_fm350_transport').replace('/sys/',d+'/')
            code='''log() { :; }; warn() { :; }; fm350_set_usb_power() { :; }
fm350_install_mm_ignore_rule() { :; }; udevadm() { :; }
fm350_find_rndis_iface() { return 1; }
'''+fn+'''
for TRANSPORT_MODE in usb pcie auto; do
 detect_fm350_transport || exit 1
 echo "$TRANSPORT_MODE:$FM350_TRANSPORT:$FM350_USB_ID"
done
'''
            self.assertEqual(run(code).splitlines(),['usb:usb:0e8d:7127','pcie:pcie:','auto:pcie:'])
    def test_marker_does_not_hide_modem_reset(self):
        with tempfile.TemporaryDirectory() as d:
            for state,expected in [('1',False),('0',True)]:
                marker=Path(d)/'marker';marker.write_text('old boot marker')
                code=f'''FM350_AVAILABLE=1; MODEM_KEY=test
log() {{ :; }}; detect_modem_unlock_kind() {{ echo fm350-fcc; }}
fm350_find_at_port() {{ :; }}; fm350_query_identity() {{ :; }}
unlock_marker_path() {{ echo '{marker}'; }}
fm350_at_cmd() {{ echo '+GTFCCLOCKVER: {state}'; }}
fm350_unlock() {{ echo UNLOCK; }}
'''+function('perform_modem_unlock')+'\nperform_modem_unlock'
                self.assertEqual('UNLOCK' in run(code),expected)
    def test_failed_unlock_has_no_success_marker(self):
        with tempfile.TemporaryDirectory() as d:
            marker=Path(d)/'marker'
            code=f'''FM350_AVAILABLE=1; MODEM_KEY=test
log() {{ :; }}; detect_modem_unlock_kind() {{ echo fm350-fcc; }}
fm350_find_at_port() {{ :; }}; fm350_query_identity() {{ :; }}
unlock_marker_path() {{ echo '{marker}'; }}
fm350_unlock() {{ return 1; }}
'''+function('perform_modem_unlock')+'\nif perform_modem_unlock; then exit 2; fi'
            run(code);self.assertFalse(marker.exists())
    def test_service_templates_current_image_and_ordering(self):
        with tempfile.TemporaryDirectory() as d:
            assignments='\n'.join(f'{key}="{d}/{key}"' for key in ['UNLOCK_SERVICE_PATH','SERVICE_PATH','FAILOVER_SCRIPT_PATH','FAILOVER_SERVICE_PATH'])
            run(assignments+'''\nSELF_PATH=/usr/local/share/vyos-arm64-firstboot/modem-connect.sh
CONFIG_FILE=/config/modem-connect/modem-connect.conf
ROUTE_CACHE=/config/modem-connect/modem-route.conf
RESTORE_ONLY=1
systemctl() { :; }
'''+LIB+'\nwrite_unlock_service_unit\nwrite_service_unit\nwrite_failover_service_unit')
            connect=(Path(d)/'SERVICE_PATH').read_text()
            self.assertIn('Requires=vyos-router.service modem-unlock.service',connect)
            self.assertIn('modem-connect.sh --service-run',connect)
            unlock=(Path(d)/'UNLOCK_SERVICE_PATH').read_text()
            self.assertIn('--service-run --unlock-only',unlock)
            self.assertIn('Restart=on-failure',unlock)
            subprocess.run(['bash','-n',str(Path(d)/'FAILOVER_SCRIPT_PATH')],check=True)
    def test_quectel_configuration_has_no_unlock_unit_or_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            config=root/'config';config.write_text('UNLOCK_KIND=none\n')
            unlock=root/'unlock';unlock.write_text('stale FM350 unit')
            code=f'CONFIG_FILE="{config}"; UNLOCK_SERVICE_PATH="{unlock}"; SERVICE_PATH="{root}/connect"; SELF_PATH=/image/modem-connect.sh\n'
            code+='systemctl() { :; }\n'+LIB+'\nwrite_unlock_service_unit; write_service_unit'
            run(code)
            self.assertFalse(unlock.exists())
            self.assertNotIn('modem-unlock.service',(root/'connect').read_text())

    def test_legacy_migration_and_fresh_image_restore(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for sub in ['etc/systemd/system','etc/udev/rules.d','usr/local/sbin','bin','image']:
                (root/sub).mkdir(parents=True)
            script=root/'image/modem-connect.sh'
            # Isolate filesystem destinations and emulate an administrator.
            fixture=SRC.replace('/etc/',d+'/etc/').replace('/usr/local/sbin/',d+'/usr/local/sbin/')
            fixture=fixture.replace('[ "$EUID" -eq 0 ]','true')
            script.write_text(fixture)
            (root/'image/modem-services.sh').write_text(LIB)
            (root/'image/modem-native-wwan.sh').write_text((ROOT/'tools/common-firstboot/modem-native-wwan.sh').read_text())
            for name,body in [('id','echo vyattacfg'),('systemctl','echo "$*" >> "$CALL_LOG"')]:
                f=root/'bin'/name;f.write_text('#!/bin/bash\n'+body+'\n');f.chmod(0o755)
            env=dict(os.environ, PATH=str(root/'bin')+':'+os.environ['PATH'],
                     PERSIST_DIR=str(root/'persist'), CALL_LOG=str(root/'calls'))
            def restore():
                subprocess.run(['bash',str(script),'--restore-services'],env=env,check=True,capture_output=True)
            restore()
            self.assertFalse((root/'calls').exists())
            legacy=root/'etc/modem-connect.conf'
            legacy.write_text('APN=internet\nTRANSPORT=usb\n')
            restore()
            config=root/'persist/modem-connect.conf'
            self.assertEqual(config.read_text(),legacy.read_text())
            self.assertEqual(config.stat().st_mode & 0o777,0o600)
            config.write_text('APN=keep-this\nTRANSPORT=pcie\n')
            # New image: all generated units/monitor removed, /config survives.
            for f in (root/'etc/systemd/system').iterdir(): f.unlink()
            for f in (root/'usr/local/sbin').iterdir(): f.unlink()
            restore()
            self.assertIn('APN=keep-this',config.read_text())
            unit=(root/'etc/systemd/system/modem-connect.service').read_text()
            self.assertIn(str(script)+' --service-run',unit)
            self.assertIn('start --no-block modem-connect.service',(root/'calls').read_text())

    def test_restore_and_probe_without_service_mutations(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'bin').mkdir()
            for name,body in [('id','echo vyattacfg'),('systemctl','echo unexpected-service-mutation >&2; exit 99')]:
                f=p/'bin'/name;f.write_text('#!/bin/bash\n'+body+'\n');f.chmod(0o755)
            # Run the actual script with isolated persistent paths and no config.
            import os
            env=dict(os.environ,PATH=str(p/'bin')+':'+os.environ['PATH'],PERSIST_DIR=str(p/'persist'),CONFIG_FILE=str(p/'absent'))
            result=subprocess.run(['bash',str(ROOT/'tools/common-firstboot/modem-connect.sh'),'--probe'],env=env,text=True,capture_output=True,check=True)
            self.assertNotIn('unexpected-service-mutation',result.stderr)
            self.assertFalse((p/'persist').exists())
if __name__=='__main__': unittest.main()
