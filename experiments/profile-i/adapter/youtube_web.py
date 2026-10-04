"""Profile I: YouTube URLs are browser pages, never download jobs."""
from functools import wraps
from urllib.parse import urlsplit

def is_youtube(uri):
    try:
        url=urlsplit(uri)
        host=(url.hostname or '').lower()
        return url.scheme in ('http','https') and any(host==d or host.endswith('.'+d) for d in ('youtube.com','youtu.be','youtube-nocookie.com'))
    except (ValueError,TypeError):
        return False

def install():
    from anthias_server.api.serializers.mixins import CreateAssetSerializerMixin
    from anthias_server.api.serializers.v1_1 import CreateAssetSerializerV1_1
    from anthias_server.settings import settings
    for cls in (CreateAssetSerializerMixin,CreateAssetSerializerV1_1):
        original=cls.prepare_asset
        if getattr(original,'_youtube_web',False):continue
        def wrapper(original):
            @wraps(original)
            def prepare(self,data,*args,**kwargs):
                if is_youtube(data.get('uri','')):
                    data=dict(data,mimetype='webpage')
                    if not data.get('duration') or str(data['duration'])=='0':data['duration']=int(settings['default_duration'])
                    self._pending_youtube_uri=None
                    self._pending_remote_video_uri=None
                return original(self,data,*args,**kwargs)
            prepare._youtube_web=True
            return prepare
        cls.prepare_asset=wrapper(original)

def create(request):
    from datetime import timedelta
    from django.http import HttpResponse
    from django.utils import timezone
    from anthias_server.app import views
    from anthias_server.app.models import Asset
    from anthias_server.settings import settings
    if request.method!='POST':return HttpResponse(status=405)
    uri=(request.POST.get('uri') or '').strip()
    if not is_youtube(uri):return views.assets_create(request)
    from anthias_common.utils import validate_url
    if not validate_url(uri):return HttpResponse('Invalid URL',status=400)
    now=timezone.now()
    Asset.objects.create(name=uri,uri=uri,mimetype='webpage',duration=int(settings['default_duration']),is_enabled=True,is_processing=False,play_order=Asset.objects.filter(is_enabled=True,is_processing=False).count(),start_date=now,end_date=now+timedelta(days=30))
    return views._asset_table_response(request,toast=('success','Webpage added'),offer_review_cta=False)
