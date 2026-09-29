#!/usr/bin/env python3
"""Content inventory for comparing equivalent builds without timestamp noise."""
from pathlib import Path
import hashlib,json,os,stat
root=Path('/work/verification/root')
items={}
for parent,dirs,files in os.walk(root,followlinks=False):
    for name in sorted(dirs+files):
        p=Path(parent)/name;rel=str(p.relative_to(root));s=p.lstat()
        row={'mode':stat.S_IMODE(s.st_mode),'uid':s.st_uid,'gid':s.st_gid}
        if p.is_symlink():row.update(type='link',target=os.readlink(p))
        elif p.is_file():
            if p.suffix=='.pyc':continue
            with p.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
            row.update(type='file',size=s.st_size,sha256=h)
        elif p.is_dir():row['type']='directory'
        else:row.update(type='special',device=s.st_rdev)
        items[rel]=row
out=Path('/work/output/content-inventory.json')
out.write_text(json.dumps({'schema':1,'omitted':['mtime','atime','ctime','*.pyc'],'entries':items},sort_keys=True,separators=(',',':'))+'\n')
print('Inventory entries:',len(items))
