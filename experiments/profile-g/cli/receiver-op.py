#!/usr/bin/env python3
"""Read-only wireless preflight. No AP, interface or driver changes."""
import json
from pathlib import Path
import sys
from vyos.receiver import wifi_report

def main():
    interfaces = sys.argv[1:] or [p.name for p in Path('/sys/class/net').iterdir() if (p/'phy80211').exists()]
    for interface in interfaces:
        try:
            print(json.dumps(wifi_report(interface),indent=2))
        except Exception as error:
            print(json.dumps({'interface':interface,'ready_for_exclusive_miracast':False,'reason':str(error)}))
if __name__=='__main__': main()
