#!/usr/bin/env python3
"""Avoid reapplying the IOMMU auto-gating fix already in Linux 6.18.54.

Only the recognized upstream backport is handled; all other patch context is
still checked by patch --fuzz=0. Older kernels retain the original patch.
"""
import argparse
import re
from pathlib import Path


def prepare(patch, source):
    marker = '#define DISABLE_FETCH_DTE_TIME_LIMIT'
    if marker not in source:
        return patch
    expected = ('auto_gate = rk_iommu_read(iommu->bases[i], RK_MMU_AUTO_GATING);',
                'auto_gate |= DISABLE_FETCH_DTE_TIME_LIMIT;',
                'rk_iommu_write(iommu->bases[i], RK_MMU_AUTO_GATING, auto_gate);')
    if not all(line in source for line in expected):
        raise RuntimeError('Unrecognized upstream IOMMU gating implementation')
    if not re.search(r'#define DISABLE_FETCH_DTE_TIME_LIMIT\s+BIT\(31\)', source):
        raise RuntimeError('Unexpected IOMMU gating bit')
    # Drop the now-upstream macro hunk, not any unrelated MPP changes.
    pattern = r'@@ -41,6 \+43,8 @@\n.*?(?=@@)'
    patch, count = re.subn(pattern, '', patch, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError('MPP macro hunk changed; review required')
    replacement = '''@@ -955,6 +1047,8 @@ static int rk_iommu_enable(struct rk_iommu *iommu)
 	}
 
 	ret = rk_iommu_enable_paging(iommu);
+	if (!ret)
+		iommu->iommu_enabled = true;
 
 out_disable_stall:
 	rk_iommu_disable_stall(iommu);
'''
    pattern = r'@@ -948,9 \+1040,14 @@.*?(?=@@)'
    patch, count = re.subn(pattern, lambda _: replacement, patch, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError('MPP enable hunk changed; review required')
    return patch


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', type=Path)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(prepare(args.patch.read_text(), args.source.read_text()))
