from pathlib import Path
import difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-iommu-test4')
out=base.parent/'av1-reset-candidates-20260922'
s=(base/'source/drivers/iommu/vsi-iommu.c').read_text();old=s
pos=s.index('static void vsi_iommu_flush_tlb_all')
params='''/* Diagnostic A/B switches: change only with all AV1 clients stopped. */
static bool vyarm_identity_guard;
module_param(vyarm_identity_guard, bool, 0644);
MODULE_PARM_DESC(vyarm_identity_guard, "TEST ONLY: guard identity-domain runtime resume");
static bool vyarm_nonsleeping_tlb;
module_param(vyarm_nonsleeping_tlb, bool, 0644);
MODULE_PARM_DESC(vyarm_nonsleeping_tlb, "TEST ONLY: active-only TLB invalidation");

'''
s=s[:pos]+params+s[pos:]
start=s.index('static void vsi_iommu_flush_tlb_all');end=s.index('static irqreturn_t',start)
part=s[start:end]
part=part.replace('ret = pm_runtime_resume_and_get(iommu->dev);\n\t\tif (ret < 0)\n\t\t\tcontinue;', '''if (READ_ONCE(vyarm_nonsleeping_tlb)) {
			ret = pm_runtime_get_if_active(iommu->dev);
			dev_info_ratelimited(iommu->dev,
				"VYARM_TLB active-only ret=%d\\n", ret);
			if (ret <= 0)
				continue;
		} else {
			ret = pm_runtime_resume_and_get(iommu->dev);
			if (ret < 0)
				continue;
		}''')
s=s[:start]+part+s[end:]
needle='writel(VSI_MMU_BIT_ENABLE, iommu->regs + VSI_MMU_AHB_CONTROL_BASE);'
assert s.count(needle)==1
s=s.replace(needle,needle+'''
	if (READ_ONCE(vyarm_nonsleeping_tlb)) {
		writel(VSI_MMU_BIT_FLUSH, iommu->regs + VSI_MMU_FLUSH_BASE);
		writel(0, iommu->regs + VSI_MMU_FLUSH_BASE);
		dev_info_ratelimited(iommu->dev, "VYARM_TLB enable flush\\n");
	}''')
start=s.index('static int __maybe_unused vsi_iommu_resume')
part=s[start:]
needle='\tif (iommu->domain) {'
assert part.count(needle)==1
part=part.replace(needle,'''\tif (READ_ONCE(vyarm_identity_guard) &&
	    iommu->domain == &vsi_identity_domain) {
		dev_info_ratelimited(iommu->dev, "VYARM_IDENTITY resume guard hit\\n");
		return 0;
	}
	if (iommu->domain) {''')
s=s[:start]+part
(out/'vsi-iommu.c').write_text(s)
(out/'candidate.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='a/drivers/iommu/vsi-iommu.c',tofile='b/drivers/iommu/vsi-iommu.c')))
print('Candidate prepared')
