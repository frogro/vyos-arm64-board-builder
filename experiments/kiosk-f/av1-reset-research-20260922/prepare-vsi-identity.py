from pathlib import Path
import difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-iommu-test4')
out=base.parent/'av1-reset-research-20260922'/'identity-candidate';out.mkdir(exist_ok=False)
src=base/'source/drivers/iommu/vsi-iommu.c';old=src.read_text();new=old.replace('if (iommu->domain) {\n\t\tstruct vsi_iommu_domain *vsi_domain = to_vsi_domain(iommu->domain);','/* Identity is a standalone iommu_domain, not a vsi_iommu_domain. */\n\tif (iommu->domain && iommu->domain != &vsi_identity_domain) {\n\t\tstruct vsi_iommu_domain *vsi_domain = to_vsi_domain(iommu->domain);')
assert old!=new
(out/'vsi-iommu.c').write_text(new)
(out/'Makefile').write_text('obj-m += vsi-iommu.o\nccflags-y += -I'+str(base/'source/drivers/iommu')+'\n')
repo=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/worktrees/kiosk-profile-f/experiments/kiosk-f/av1-reset-research-20260922')
(repo/'vsi-identity-resume-guard-candidate.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/drivers/iommu/vsi-iommu.c',tofile='b/drivers/iommu/vsi-iommu.c')))
