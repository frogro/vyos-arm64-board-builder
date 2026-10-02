#!/usr/bin/env python3
"""Flatten the stripped graphics base so removed F payload is absent from layers."""
import json,subprocess,sys
base,tag=sys.argv[1:]
subprocess.run(['docker','build','--network=none','--build-arg','BASE_IMAGE='+base,'-f','repo/experiments/profile-g/container/Containerfile.graphics-base','-t',tag+'-stripped','repo'],check=True)
container=subprocess.check_output(['docker','create',tag+'-stripped'],text=True).strip()
try:
    config=json.loads(subprocess.check_output(['docker','image','inspect',tag+'-stripped']))[0]['Config']
    args=['docker','import']
    for entry in config.get('Env') or []:args+=['--change','ENV '+entry]
    export=subprocess.Popen(['docker','export',container],stdout=subprocess.PIPE)
    try:
        subprocess.run(args+['-',tag],stdin=export.stdout,check=True)
    finally:
        export.stdout.close()
        code=export.wait()
    if code:raise RuntimeError('Graphics base export failed')
finally:subprocess.run(['docker','rm',container],check=True)
subprocess.run(['docker','run','--rm','--entrypoint','/bin/sh',tag,'-ec',
                'test -x /usr/bin/weston; test ! -e /opt/vyarm/chromium/chrome; ! command -v sunshine; ! command -v chromium'],check=True)
