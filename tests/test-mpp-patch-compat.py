#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('compat',ROOT/'tools/prepare-rk3588-mpp-patch.py')
compat=importlib.util.module_from_spec(spec);spec.loader.exec_module(compat)
PATCH=(ROOT/'profiles/base-hardware/kernel-patches/rk3588-synopsys-hdmirx/0001-rk3588-mpp-rkvenc2-6.18.patch').read_text()
UPSTREAM='''#define DISABLE_FETCH_DTE_TIME_LIMIT BIT(31)
auto_gate = rk_iommu_read(iommu->bases[i], RK_MMU_AUTO_GATING);
auto_gate |= DISABLE_FETCH_DTE_TIME_LIMIT;
rk_iommu_write(iommu->bases[i], RK_MMU_AUTO_GATING, auto_gate);
'''
class Compat(unittest.TestCase):
    def test_old_kernel_unchanged(self):
        self.assertEqual(compat.prepare(PATCH,''),PATCH)
    def test_upstream_backport_keeps_mpp_state(self):
        out=compat.prepare(PATCH,UPSTREAM)
        self.assertNotIn('+#define DISABLE_FETCH_DTE_TIME_LIMIT',out)
        self.assertNotIn('+\t\t\t       DISABLE_FETCH_DTE_TIME_LIMIT);',out)
        self.assertIn('+\t\tiommu->iommu_enabled = true;',out)
        before,after=PATCH.split('diff --git a/drivers/iommu/rockchip-iommu.c',1)
        self.assertTrue(out.startswith(before))
        self.assertEqual(out.split('diff --git a/drivers/video/Kconfig',1)[1],PATCH.split('diff --git a/drivers/video/Kconfig',1)[1])
    def test_unknown_backport_fails(self):
        with self.assertRaises(RuntimeError):compat.prepare(PATCH,'#define DISABLE_FETCH_DTE_TIME_LIMIT BIT(30)')
    def test_changed_patch_fails(self):
        with self.assertRaises(RuntimeError):compat.prepare(PATCH.replace('@@ -948,9 +1040,14 @@','@@ -948,9 +1040,15 @@'),UPSTREAM)
if __name__=='__main__':unittest.main()
