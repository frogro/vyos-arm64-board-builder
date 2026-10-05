from pathlib import Path
HERE=Path(__file__).resolve().parent

def prepare(root):
    root=Path(root)
    files={
      'interface-definitions/service_signage.xml.in':(HERE/'service_signage.xml').read_text(),
      'src/conf_mode/service_signage.py':(HERE/'service.py').read_text(),
      'src/helpers/vyarm-signage-supervisor.py':(HERE/'supervisor.py').read_text(),
      'src/systemd/vyarm-signage.service': '[Unit]\nDescription=VyARM media administration and player\nAfter=network.target\nConditionPathExists=/run/vyarm-signage/config.json\n[Service]\nExecStart=/usr/bin/python3 /usr/libexec/vyos/vyarm-signage-supervisor.py\nRestart=on-failure\nRestartSec=5\nKillMode=mixed\nTimeoutStopSec=90\n',
    }
    for name in files:
        if (root/name).exists():raise ValueError('Existing profile source: '+name)
    for name,text in files.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(0o755 if name.endswith('.py') else 0o644)
    return sorted(files)
