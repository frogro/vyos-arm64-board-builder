"""Time-window policy for F; blanking is not physical display power-off."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re
DAYS=('mon','tue','wed','thu','fri','sat','sun')
def validate(cfg):
 if not isinstance(cfg,dict) or set(cfg)-{'start','stop','days','timezone'}:raise ValueError('Unknown display schedule field')
 for key in ('start','stop'):
  if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',cfg.get(key,'')):raise ValueError('Display schedule requires start and stop HH:MM')
 if cfg['start']==cfg['stop']:raise ValueError('Start and stop must differ; remove schedule for continuous display')
 days=cfg.get('days',','.join(DAYS)).split(',')
 if not days or len(set(days))!=len(days) or any(d not in DAYS for d in days):raise ValueError('Invalid display schedule days')
 zone=cfg.get('timezone','UTC')
 if not re.fullmatch(r'[A-Za-z0-9_+/-]+',zone):raise ValueError('Invalid timezone')
 try:ZoneInfo(zone)
 except Exception:raise ValueError('Unknown display timezone')
 return dict(start=cfg['start'],stop=cfg['stop'],days=','.join(days),timezone=zone)
def active(env,now=None):
 if not env.get('KIOSK_DISPLAY_START'):return True
 cfg=validate({k:env.get('KIOSK_DISPLAY_'+k.upper(),'') for k in ('start','stop','days','timezone')})
 current=(now or datetime.now(ZoneInfo(cfg['timezone']))).astimezone(ZoneInfo(cfg['timezone']))
 minute=current.hour*60+current.minute
 start,stop=[int(t[:2])*60+int(t[3:]) for t in (cfg['start'],cfg['stop'])]
 day=current.weekday()
 if start<stop:return DAYS[day] in cfg['days'].split(',') and start<=minute<stop
 if minute>=start:return DAYS[day] in cfg['days'].split(',')
 return minute<stop and DAYS[(day-1)%7] in cfg['days'].split(',')
