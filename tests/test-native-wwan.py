#!/usr/bin/env python3
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
LIB=(ROOT/'tools/common-firstboot/modem-native-wwan.sh').read_text()

def run(code):
    return subprocess.run(['bash','-c',code],capture_output=True,text=True,check=True).stdout

class NativeWwan(unittest.TestCase):
    def test_device_mapping_rejects_mismatched_modem_and_non_wwan(self):
        code=LIB+'''
MM_AVAILABLE=1; MODEM=2; NET_PORTS=$'rmnet0\nwwan2'
native_wwan_interface; echo
MODEM=0
if native_wwan_interface; then exit 1; fi
MODEM=2; NET_PORTS=eth1
if native_wwan_interface; then exit 2; fi
'''
        self.assertEqual(run(code).strip(),'wwan2')
    def test_success_uses_native_config_and_no_static_lease(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            wrapper=root/'op'; wrapper.write_text('#!/bin/sh\necho "set firewall ipv4 name VYOS-WAN-IN default-action drop"\n');wrapper.chmod(0o755)
            lib=LIB.replace('/opt/vyatta/bin/vyatta-op-cmd-wrapper',str(wrapper))
            code=lib+f'''
MM_AVAILABLE=1; MODEM=2; NET_PORTS=wwan2
CONFIG_FILE={d}/settings; ROUTE_CACHE={d}/route; APN_CACHE={d}/apn; MUX_CACHE={d}/mux; BACKEND_CACHE={d}/backend
APN=internet; WWAN_ROUTE_DISTANCE=200; WWAN_NAT_RULE=160; WWAN_FORWARD_RULE=11; AP_NET=10.3.141.0/24
TRANSPORT_MODE=auto; MODEM_UNLOCK_KIND=none; MODEM_DEVICE_ID=test; MODEM_EQUIPMENT_ID=test
log() {{ :; }}; warn() {{ :; }}; die() {{ exit 1; }}
systemctl() {{ return 0; }}; ip() {{ echo '2: wwan2 inet 10.2.3.4/24'; }}; ping() {{ return 0; }}
native_cli_transaction() {{ cat >> {d}/commands; }}
write_native_service_unit() {{ echo native > {d}/service; }}
try_native_wwan
'''
            run(code)
            commands=(root/'commands').read_text()
            self.assertIn('set interfaces wwan wwan2 apn internet',commands)
            self.assertIn('dhcp-options default-route-distance 200',commands)
            self.assertNotIn('10.2.3.4',commands)
            self.assertIn('inbound-interface name wwan2',commands)
            self.assertIn('MANAGEMENT=vyos',(root/'settings').read_text())
            self.assertNotIn('APN=',(root/'settings').read_text())
    def test_failover_uses_selected_interfaces_and_dhcp_gateways(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            wrapper = root/'op'
            wrapper.write_text("#!/bin/sh\necho \"set interfaces ethernet eth7 address 'dhcp'\"\necho \"set interfaces wwan wwan2 address 'dhcp'\"\n")
            wrapper.chmod(0o755)
            lib = LIB.replace('/opt/vyatta/bin/vyatta-op-cmd-wrapper', str(wrapper))
            code = lib + f"""
WIRED_WAN=eth7; PERSIST_DIR={d}; UNLOCK_STATE_DIR={d}
FAILOVER_WIRED_TARGETS='4.2.2.1 4.2.2.2'; FAILOVER_MOBILE_TARGETS='8.8.4.4'
log() {{ :; }}; warn() {{ :; }}; die() {{ exit 1; }}
native_cli_transaction() {{ cat >> {d}/commands; }}
configure_native_failover wwan2
"""
            run(code)
            commands = (root/'commands').read_text()
            self.assertIn('static route 4.2.2.1/32 dhcp-interface eth7', commands)
            self.assertIn('static route 8.8.4.4/32 dhcp-interface wwan2', commands)
            self.assertIn('dhcp-interface eth7 metric 10', commands)
            self.assertNotIn('192.168.', commands)
            self.assertNotIn('next-hop', commands)
            restore = (root/'native-failover-restore.commands').read_text()
            self.assertIn('delete protocols failover route 0.0.0.0/0 2>', restore)
            self.assertNotIn('delete protocols failover route 0.0.0.0/0 dhcp-interface', restore)
            self.assertIn('default-route-distance 255', commands)
            self.assertNotIn('set interfaces ethernet eth7 dhcp-options no-default-route', commands)

    def test_failover_refuses_existing_admin_route(self):
        with tempfile.TemporaryDirectory() as d:
            wrapper = Path(d)/'op'
            wrapper.write_text("#!/bin/sh\necho 'set protocols failover route 0.0.0.0/0 next-hop 192.0.2.1 interface eth9'\n")
            wrapper.chmod(0o755)
            code = LIB.replace('/opt/vyatta/bin/vyatta-op-cmd-wrapper', str(wrapper)) + f"""
WIRED_WAN=eth7; PERSIST_DIR={d}; UNLOCK_STATE_DIR={d}
die() {{ exit 42; }}
native_cli_transaction() {{ touch {d}/unexpected; }}
configure_native_failover wwan2
"""
            result = subprocess.run(['bash', '-c', code], capture_output=True)
            self.assertEqual(result.returncode, 42)
            self.assertFalse((Path(d)/'unexpected').exists())

    def test_native_service_replaces_old_dialers(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'etc/systemd/system').mkdir(parents=True)
            code=LIB.replace('/etc/',d+'/etc/')+f'''
SELF_PATH=/image/modem-connect.sh
SERVICE_PATH={d}/connect; UNLOCK_SERVICE_PATH={d}/unlock
FAILOVER_SERVICE_PATH={d}/failover; FAILOVER_SCRIPT_PATH={d}/monitor
systemctl() {{ echo "$*" >> {d}/calls; }}
write_native_service_unit
'''
            run(code)
            unit=(root/'etc/systemd/system/vyos-modem-hardware.service').read_text()
            self.assertIn('--native-prepare',unit)
            self.assertNotIn('--service-run',unit)
            self.assertIn('disable --now modem-wan-failover.service modem-connect.service modem-unlock.service',(root/'calls').read_text())

if __name__ == '__main__': unittest.main()
