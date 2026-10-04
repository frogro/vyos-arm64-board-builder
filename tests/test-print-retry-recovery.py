#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recover',ROOT/'experiments/profile-e/container/resume-usb-jobs.py')
m=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{'cups':types.ModuleType('cups')}):spec.loader.exec_module(m)
class Recovery(unittest.TestCase):
 def test_only_automatic_usb_retry_holds(self):
  a={'job-state':4,'job-state-reasons':['resources-are-not-ready'],'job-hold-until':'no-hold','job-printer-uri':'ipp://localhost/printers/RX1'}
  p={'RX1':{'device-uri':'gutenprint53+usb://dnp-dsrx1/test','printer-state':3}}
  self.assertTrue(m.recoverable(a,p))
  normalized=dict(a,**{'job-state-reasons':'none','job-printer-state-reasons':['offline-report']})
  self.assertTrue(m.recoverable(normalized,p))
  self.assertFalse(m.recoverable(dict(normalized,**{'job-hold-until':'indefinite'}),p))
  self.assertFalse(m.recoverable(dict(normalized,**{'job-printer-state-reasons':[]}),p))
  for key,value in [('job-state',3),('job-state',7),('job-state',8),('job-hold-until','indefinite'),('job-state-reasons',['cups-held-for-authentication'])]:
   self.assertFalse(m.recoverable(dict(a,**{key:value}),p))
  self.assertFalse(m.recoverable(a,{'RX1':{'device-uri':'ipp://other/printer','printer-state':3}}))
  self.assertFalse(m.recoverable(a,{'RX1':{'device-uri':p['RX1']['device-uri'],'printer-state':5}}))
if __name__=='__main__':unittest.main()
