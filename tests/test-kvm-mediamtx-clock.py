#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('guard',root/'tools/kvm-cli/vyos-kvm-mediamtx-supervisor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Tests(unittest.TestCase):
    def test_waits_for_sync_then_tolerates_offline_ntp(self):
        self.assertFalse(m.decision(True,False,False,False))
        self.assertTrue(m.decision(True,False,True,False))
        self.assertTrue(m.decision(True,True,False,False))
    def test_clock_jump_requires_revalidation(self):
        self.assertFalse(m.decision(True,True,False,True))
        self.assertTrue(m.decision(True,True,True,True))
    def test_disabled_moq_stays_disabled(self):
        self.assertFalse(m.decision(False,False,True,True))
    def test_missing_or_unresponsive_chrony_is_not_ready(self):
        for exc in (FileNotFoundError(),subprocess.TimeoutExpired('chronyc',3)):
            with patch.object(m.subprocess,'run',side_effect=exc):
                self.assertFalse(m.synchronized())

if __name__=='__main__': unittest.main()
