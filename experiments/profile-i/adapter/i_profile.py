"""Pinned Anthias upload policy for browser playback."""
import os

def configure():
    from anthias_server import processing
    key='vyarm-browser-player'
    os.environ['DEVICE_TYPE']=key
    processing._HW_DECODE_VIDEO_CODECS[key]=frozenset({'h264','hevc','vp8','vp9','av1'})
    original = getattr(processing, '_vyarm_original_pixel_cap', processing._pixel_cap_rejection)
    processing._vyarm_original_pixel_cap = original
    def pixel_cap(width, height, device_key):
        if device_key == key:
            if width and height and (max(width, height) > 3840 or min(width, height) > 2160):
                return 'Video uploads support up to 3840x2160 (4K UHD), or 2160x3840 portrait. Please resize this video before uploading.'
            return None
        return original(width, height, device_key)
    processing._pixel_cap_rejection = pixel_cap

if __name__=='__main__':
    import django
    django.setup()
    configure()
    from anthias_server.celery_tasks import celery
    celery.worker_main(['worker','-B','--concurrency=1','--loglevel=warning'])
