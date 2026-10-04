import importlib.util,datetime,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('schedule',Path(__file__).resolve().parents[1]/'cli/kiosk_schedule.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Schedule(unittest.TestCase):
 def test_boundaries_overnight(self):
  e={'KIOSK_DISPLAY_START':'18:00','KIOSK_DISPLAY_STOP':'06:00','KIOSK_DISPLAY_DAYS':'fri','KIOSK_DISPLAY_TIMEZONE':'Europe/Berlin'}
  for t,want in [('2026-10-02T17:59:00+02:00',False),('2026-10-02T18:00:00+02:00',True),('2026-10-03T05:59:00+02:00',True),('2026-10-03T06:00:00+02:00',False),('2026-10-03T18:00:00+02:00',False)]:self.assertEqual(m.active(e,datetime.datetime.fromisoformat(t)),want)
 def test_invalid_and_disabled(self):
  self.assertTrue(m.active({}))
  for c in [dict(start='25:00',stop='06:00'),dict(start='06:00',stop='06:00'),dict(start='08:00',stop='09:00',days='fry'),dict(start='08:00',stop='09:00',timezone='Fake/Zone')]:
   with self.assertRaises(ValueError):m.validate(c)
 def test_daytime_and_timezone(self):
  e={'KIOSK_DISPLAY_START':'08:00','KIOSK_DISPLAY_STOP':'18:00','KIOSK_DISPLAY_DAYS':'sun','KIOSK_DISPLAY_TIMEZONE':'Europe/Berlin'}
  self.assertTrue(m.active(e,datetime.datetime.fromisoformat('2026-10-04T06:00:00+00:00')))
  self.assertFalse(m.active(e,datetime.datetime.fromisoformat('2026-10-04T16:00:00+00:00')))
if __name__=='__main__':unittest.main()
