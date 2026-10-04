"""Bound HTTP uploads before Django/ASGI spools their request bodies."""
import asyncio
import json
import os
from pathlib import Path
import re
import shutil
import time

GIB=1024**3
class Rejected(Exception):
    def __init__(self,message,status=413):self.message=message;self.status=status

def used_bytes(root):
    seen=set();total=0
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in files:
            try:
                p=Path(parent)/name
                if p.is_symlink():continue
                s=p.stat();key=(s.st_dev,s.st_ino)
                if key not in seen:total+=s.st_size;seen.add(key)
            except FileNotFoundError:pass
    return total

def budget(headers,root,quota,max_file,reserve):
    try:size=int(headers.get('content-length',''))
    except ValueError:raise Rejected('Die Upload-Größe fehlt. Bitte die Datei erneut über den Browser auswählen.',411)
    if size<0:raise Rejected('Ungültige Upload-Größe.',400)
    total=size
    if 'content-range' in headers:
        match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',headers['content-range'])
        if not match:raise Rejected('Ungültiger Upload-Bereich.',400)
        start,end,total=map(int,match.groups())
        if not 0<=start<=end<total:raise Rejected('Ungültiger Upload-Bereich.',400)
        # Account for previously stored chunks in used_bytes; reserve remaining bytes.
        additional=max(size,total-start)
    else:additional=size
    if total>max_file+1048576:raise Rejected(f'Die Datei überschreitet die Upload-Grenze von {max_file/GIB:g} GiB.')
    if used_bytes(root)+additional>quota:raise Rejected('Der Medienspeicher ist voll. Bitte nicht mehr benötigte Inhalte löschen.')
    if shutil.disk_usage(root).free<reserve+3*additional:raise Rejected('Zu wenig freier Speicher für diesen Upload und seine Verarbeitung. Bitte Inhalte löschen.')
    return size

class Guard:
    def __init__(self,app,root='/data'):
        self.app=app;self.root=Path(root);self.lock=asyncio.Lock()
        self.quota=int(os.getenv('I_STORAGE_LIMIT_BYTES',str(8*GIB)))
        self.max_file=int(os.getenv('I_UPLOAD_LIMIT_BYTES',str(2*GIB)))
        self.reserve=int(os.getenv('I_FREE_RESERVE_BYTES',str(GIB)))
    async def reject(self,send,error):
        body=json.dumps({'error':error.message,'message':error.message}).encode()
        await send({'type':'http.response.start','status':error.status,'headers':[(b'content-type',b'application/json; charset=utf-8'),(b'content-length',str(len(body)).encode())]})
        await send({'type':'http.response.body','body':body})
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method') not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        headers={k.decode().lower():v.decode() for k,v in scope.get('headers',[])}
        upload=('multipart/form-data' in headers.get('content-type','') or 'content-range' in headers or headers.get('content-type','').startswith('application/octet-stream'))
        if not upload:return await self.app(scope,receive,send)
        if self.lock.locked():return await self.reject(send,Rejected('Ein anderer Upload läuft. Bitte kurz warten.',409))
        async with self.lock:
            started=False;received=0
            try:
                size=await asyncio.to_thread(budget,headers,self.root,self.quota,self.max_file,self.reserve)
                async def guarded_receive():
                    nonlocal received
                    message=await receive()
                    if message['type']=='http.request':
                        received+=len(message.get('body',b''))
                        if received>size:raise Rejected('Upload größer als angekündigt.')
                        if shutil.disk_usage(self.root).free<self.reserve:raise Rejected('Upload gestoppt: freier Speicher reicht nicht aus.')
                    return message
                async def guarded_send(message):
                    nonlocal started
                    if message['type']=='http.response.start':started=True
                    await send(message)
                await self.app(scope,guarded_receive,guarded_send)
            except Rejected as error:
                if started:raise
                await self.reject(send,error)
