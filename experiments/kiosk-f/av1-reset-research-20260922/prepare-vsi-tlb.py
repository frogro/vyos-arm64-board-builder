from pathlib import Path
import difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-iommu-test4')
out=base.parent/'av1-reset-research-20260922'/'tlb-candidate';out.mkdir(exist_ok=False)
old=(base/'source/drivers/iommu/vsi-iommu.c').read_text()
start=old.index('static void vsi_iommu_flush_tlb_all');end=old.index('static irqreturn_t',start)
part=old[start:end].replace('ret = pm_runtime_resume_and_get(iommu->dev);\n\t\tif (ret < 0)', '''/* Cannot synchronously resume under vsi_domain->lock/irqsave.
		 * A suspended provider is invalidated when re-enabled below.
		 */
		ret = pm_runtime_get_if_active(iommu->dev);
		if (ret <= 0)''')
new=old[:start]+part+old[end:]
needle='writel(VSI_MMU_BIT_ENABLE, iommu->regs + VSI_MMU_AHB_CONTROL_BASE);'
assert new.count(needle)==1
new=new.replace(needle,needle+'''
	/* Also retire invalidations skipped while this provider was suspended. */
	writel(VSI_MMU_BIT_FLUSH, iommu->regs + VSI_MMU_FLUSH_BASE);
	writel(0, iommu->regs + VSI_MMU_FLUSH_BASE);''')
(out/'vsi-iommu.c').write_text(new)
(out/'Makefile').write_text('obj-m += vsi-iommu.o\nccflags-y += -I'+str(base/'source/drivers/iommu')+'\n')
r=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/worktrees/kiosk-profile-f/experiments/kiosk-f/av1-reset-research-20260922')
(r/'vsi-nonsleeping-tlb-candidate.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/drivers/iommu/vsi-iommu.c',tofile='b/drivers/iommu/vsi-iommu.c')))
