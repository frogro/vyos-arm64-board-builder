#!/usr/bin/env python3
"""Carry the runner's native SquashFS tools into the matching ARM64 build container."""
from pathlib import Path
import subprocess,re,shutil,hashlib,json
w=Path('/work/native-pack');w.mkdir(exist_ok=True)
gcc=Path(subprocess.check_output(['gcc','-print-file-name=libgcc_s.so.1'],text=True).strip()).resolve()
assert gcc.is_file()
files={gcc}
for tool in ('mksquashfs','unsquashfs'):
    p=Path('/usr/bin')/tool;files.add(p)
    out=subprocess.check_output(['ldd',str(p)],text=True)
    files.update(Path(x) for x in re.findall(r'(/[^\s()]+)',out))
for p in files:
    shutil.copyfile(p,w/p.name);(w/p.name).chmod(0o755)
m={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in w.iterdir() if p.is_file() and p.name!='SHA256.json'}
(w/'SHA256.json').write_text(json.dumps(m,indent=2)+'\n')
