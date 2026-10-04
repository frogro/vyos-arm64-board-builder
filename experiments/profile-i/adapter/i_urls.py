"""Local experiment: Anthias administration and scheduler, browser playback in F."""
import asyncio
import mimetypes
import re
from pathlib import Path
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse, Http404
from django.urls import path
from django.utils import timezone
from anthias_server.django_project.urls import urlpatterns as upstream
from anthias_server.api.views.v2 import _evaluate_viewer_playlist
from anthias_server.settings import settings
from anthias_server.app.models import Asset
from anthias_server.lib.auth import authorized

from i_profile import configure
configure()
from backup_limits import install as install_backup_limits
install_backup_limits()
ROOT = Path('/data/anthias_assets')

def permitted(view):
    secured = authorized(view)
    def wrapped(request, *args, **kwargs):
        if request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1'):
            return view(request, *args, **kwargs)
        return secured(request, *args, **kwargs)
    return wrapped

@permitted
def player(request):
    return HttpResponse(Path('/opt/i/player.html').read_text(), content_type='text/html')

@permitted
def playlist(request):
    settings.load()
    now = timezone.now()
    shuffle = settings['shuffle_playlist']
    rows, deadline = _evaluate_viewer_playlist(now)
    rows.sort(key=lambda a: (a.play_order, a.asset_id))
    assets=[]
    for a in rows:
        uri=a.uri or ''
        local=uri.startswith('/data/')
        assets.append(dict(id=a.asset_id, name=a.name, type=a.mimetype,
            duration=a.duration or 10,
            url='/i/media/'+a.asset_id if local else uri))
    response=JsonResponse(dict(assets=assets, now=now, deadline=deadline, shuffle=shuffle))
    response['Cache-Control']='no-store'
    return response

@permitted
def media(request, asset_id):
    if request.method not in ('GET','HEAD'):
        return HttpResponse(status=405)
    try:
        a=Asset.objects.get(asset_id=asset_id)
    except Asset.DoesNotExist:
        raise Http404
    target=Path(a.uri or '').resolve()
    if not target.is_relative_to(ROOT) or not target.is_file():
        raise Http404
    size=target.stat().st_size
    start,end=0,size-1
    status=200
    value=request.headers.get('Range')
    if value:
        match=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
        if not match or not any(match.groups()):
            return HttpResponse(status=416,headers={'Content-Range':f'bytes */{size}'})
        first,last=match.groups()
        if first:
            start=int(first); end=min(int(last),size-1) if last else size-1
        else:
            start=max(0,size-int(last))
        if start>end or start>=size:
            return HttpResponse(status=416,headers={'Content-Range':f'bytes */{size}'})
        status=206
    async def stream():
        with target.open('rb') as f:
            f.seek(start)
            left=end-start+1
            while left>0:
                chunk=await asyncio.to_thread(f.read,min(262144,left))
                if not chunk: break
                left-=len(chunk)
                yield chunk
    response=HttpResponse(status=status) if request.method=='HEAD' else StreamingHttpResponse(stream(),status=status)
    response['Content-Type']=mimetypes.guess_type(target.name)[0] or a.mimetype or 'application/octet-stream'
    response['Content-Length']=str(end-start+1)
    response['Accept-Ranges']='bytes'
    response['X-Content-Type-Options']='nosniff'
    if status==206: response['Content-Range']=f'bytes {start}-{end}/{size}'
    return response

urlpatterns=[path('i/player',player),path('i/playlist',playlist),path('i/media/<str:asset_id>',media)]+upstream

# Profile I exposes only operations relevant to the managed browser player.
from django.shortcuts import render
from anthias_server.app import views
import json

@authorized
def display(request):
    from django.shortcuts import redirect
    return redirect('/settings/#display-form')

@authorized
def status(request):
    try:
        data=json.loads(Path('/data/i-status.json').read_text())
    except (OSError,ValueError):
        data={'error':'Host status unavailable'}
    return JsonResponse(data)

@authorized
def save_settings(request):
    if request.method != 'POST': return HttpResponse(status=405)
    settings.load()
    # Removed controls must not reset unrelated upstream defaults on save.
    post=request.POST.copy()
    for key in ('audio_output','screen_rotation','show_splash','default_assets','prefer_dark_mode','debug_logging','verify_ssl','display_power_schedule_enabled','display_power_on_time','display_power_off_time'):
        value=settings.get(key, '')
        if isinstance(value,bool):
            if value:post[key]='true'
            elif key in post:del post[key]
        else:post[key]=str(value)
    days=settings.get('display_power_days','')
    post.setlist('display_power_days',days.split(',') if isinstance(days,str) else [str(x) for x in days])
    request.POST=post
    return views.settings_save(request)

def unavailable(request, **kwargs):
    return HttpResponse('This action is managed by VyOS, not Profile I.',status=404)

urlpatterns=[path('settings/save/',save_settings),path('i/display/',display),path('i/status/',status),
 path('settings/reboot/',unavailable),path('settings/shutdown/',unavailable),path('settings/display/<str:state>/',unavailable),
 path('settings/migrate-to-screenly/',unavailable)]+urlpatterns

@authorized
def apply_display(request):
    if request.method != 'POST': return HttpResponse(status=405)
    if not request.user.is_authenticated: return HttpResponse('Activate management authentication first.',status=403)
    rotation=request.POST.get('rotation','')
    output=request.POST.get('output','auto')
    if rotation not in ('0','90','180','270') or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}',output):
        return HttpResponse('Invalid display settings',status=400)
    import uuid
    job={'id':uuid.uuid4().hex,'rotation':rotation,'output':output,'muted':request.POST.get('muted')=='on'}
    if request.POST.get('schedule_enabled')=='on':
        import importlib.util
        spec=importlib.util.spec_from_file_location('schedule','/opt/i/f/kiosk-schedule.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        try:job['schedule']=module.validate({key:request.POST.get('schedule_'+key,'') for key in ('start','stop','days','timezone')})
        except ValueError as e:return HttpResponse(str(e),status=400)
    try:
        import os,uuid
        tmp=Path('/data/i-display-'+uuid.uuid4().hex+'.tmp')
        try:
            tmp.write_text(json.dumps(job))
            os.link(tmp,'/data/i-display-request.json')
        finally:tmp.unlink(missing_ok=True)
    except FileExistsError:return HttpResponse('An update is already pending.',status=409)
    from django.shortcuts import redirect
    if request.headers.get('X-Requested-With')=='XMLHttpRequest':return JsonResponse({'id':job['id']},status=202)
    return redirect('/settings/#display-form')
urlpatterns=[path('i/display/apply/',apply_display)]+urlpatterns
