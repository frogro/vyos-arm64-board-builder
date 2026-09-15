#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess
p=Path(__file__).resolve().parents[1]/'tools/kvm-cli/vyos-kvm-capture.py'
s=importlib.util.spec_from_file_location('capture',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class CaptureTests(unittest.TestCase):
 def test_sibling_metadata_caps(self):
  self.assertFalse(m.capture_caps('Video Capture\nDevice Caps : 0\n Metadata Capture\n Streaming'))
 def test_capture_and_converter(self):
  self.assertTrue(m.capture_caps('Device Caps : 0\n Video Capture\n Streaming'))
  self.assertFalse(m.capture_caps('Device Caps : 0\n Video Capture\n Video Memory-to-Memory'))
 def test_signal_and_stickiness(self):
  a=dict(device='/dev/video0',signal='present');b=dict(device='/dev/video2',signal='unknown')
  self.assertEqual(m.choose([b,a]),a)
  self.assertEqual(m.choose([b,a],previous=b['device']),b)
  a['signal']='absent';self.assertEqual(m.choose([a,b]),b)
  self.assertEqual(m.choose([a,b],previous=a['device']),a)
 def test_explicit_missing_does_not_switch(self):
  with self.assertRaises(ValueError):m.choose([dict(device='/dev/video2',signal='unknown')],explicit='/dev/video9')
 def test_gstreamer_caps_are_one_filter(self):
  runner=(p.parent/'vyos-kvm-video-runner').read_text()
  block=runner.split('        case "${FOURCC}" in',1)[1].split('        if [[ "${FOURCC}" != NV12 ]]',1)[0]
  script='FOURCC=NV12; DEVICE=/dev/video2; RESOLUTION=1920x1080; FRAMERATE=60; case "${FOURCC}" in'+block+'\nprintf "%s\\n" "${args[@]}"'
  args=subprocess.check_output(['bash','-c',script],text=True).splitlines()
  self.assertEqual(args,['v4l2src','device=/dev/video2','!','video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1'])
 def test_resolution_and_frame_rate_are_format_specific(self):
  text="""[0]: 'YUYV'
    Size: Discrete 1920x1080
      Interval: Discrete 0.017s (60.000 fps)
[1]: 'NV12'
    Size: Discrete 3840x2160
      Interval: Discrete 0.033s (30.000 fps)
"""
  c=dict(formats=['YUYV','NV12'],modes=m.parse_modes(text))
  self.assertEqual(m.compatible_formats(c,'1920x1080','60'),['YUYV'])
  self.assertEqual(m.compatible_formats(c,'3840x2160','60'),[])
  self.assertEqual(m.compatible_formats(c,'3840x2160','30'),['NV12'])
 def test_hdmi_timings_applied_before_format_check(self):
  c=dict(device='/dev/video3',signal='present',detected_size='1920x1080')
  with patch.object(m,'query',side_effect=[(0,''),(0,"Width/Height : 1920/1080\nPixel Format : 'BGR3'")]) as q:
   m.validate_size(c,'BGR3','1920x1080')
   self.assertEqual(q.call_args_list[0].args,('/dev/video3','--set-dv-bt-timings=query'))
 def test_failed_hdmi_initialization_rejects_capture(self):
  c=dict(device='/dev/video3',signal='present',detected_size='1920x1080')
  with patch.object(m,'query',return_value=(1,'')) as q:
   with self.assertRaisesRegex(ValueError,'Cannot apply'):m.validate_size(c,'BGR3','1920x1080')
   self.assertEqual(q.call_count,1)
 def test_formats(self):
  self.assertEqual(m.select_format(['NV12','YUYV'],'ffmpeg'),'NV12')
  self.assertEqual(m.select_format(['NV12','YUYV'],'gstreamer'),'NV12')
  self.assertEqual(m.select_format(['NV12','YUYV'],'ustreamer'),'YUYV')
  self.assertEqual(m.select_format(['BGR3'],'ustreamer'),'BGR3')
  with self.assertRaises(ValueError):m.select_format(['H264'],'gstreamer')
if __name__=='__main__':unittest.main()
