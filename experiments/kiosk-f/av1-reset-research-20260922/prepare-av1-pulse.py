from pathlib import Path
import shutil,difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-iommu-test4')
out=base.parent/'av1-reset-research-20260922'/'pulse-candidate'
src=base/'source/drivers/media/platform/verisilicon'
assert not out.exists();(out/'drivers/media/platform').mkdir(parents=True)
shutil.copytree(src,out/'drivers/media/platform/verisilicon')
(out/'Makefile').write_text('obj-m += drivers/media/platform/verisilicon/\n')
p=out/'drivers/media/platform/verisilicon/hantro_drv.c';old=p.read_text();new=old.replace('#include <linux/clk.h>','#include <linux/clk.h>\n#include <linux/delay.h>')
mark='int hantro_debug;'
helper='''/* Experimental only: isolate held-reset vs powered reset-pulse behavior.
 * Unlike the vendor path this does NOT implement the PMU idle handshake.
 * Restricted to the already-validated split AV1 reset resources and mask 3.
 */
static bool vyarm_test_av1_remove_pulse;
module_param(vyarm_test_av1_remove_pulse, bool, 0444);
MODULE_PARM_DESC(vyarm_test_av1_remove_pulse,
                "TEST ONLY: pulse AV1 core resets before PM/clock teardown");

static int vyarm_test_av1_pulse(struct hantro_dev *vpu)
{
	int ret, deassert_ret;

	ret = pm_runtime_resume_and_get(vpu->dev);
	if (ret < 0)
		return ret;
	ret = clk_bulk_enable(vpu->variant->num_clocks, vpu->clocks);
	if (ret)
		goto out_pm;
	dev_info(vpu->dev, "VYARM_PULSE: powered core assertion begin\\n");
	ret = vyarm_test_reset(vpu, true, 3);
	udelay(5);
	/* Always attempt to release both lines, including on partial failure. */
	deassert_ret = vyarm_test_reset(vpu, false, 3);
	dev_info(vpu->dev, "VYARM_PULSE: released cores assert=%d deassert=%d\\n",
		 ret, deassert_ret);
	if (!ret)
		ret = deassert_ret;
	clk_bulk_disable(vpu->variant->num_clocks, vpu->clocks);
out_pm:
	pm_runtime_put_sync_suspend(vpu->dev);
	return ret;
}

'''
new=new.replace(mark,helper+mark,1)
mark='\tdev_info(vpu->dev, "VYARM_PM probe: before runtime-PM setup\\n");'
new=new.replace(mark,'''\tif (vyarm_test_av1_remove_pulse &&
	    (!vpu->vyarm_test_split_resets || vyarm_test_remove_reset_mask != 3))
		return -EINVAL;

'''+mark,1)
mark='\tdev_info(vpu->dev, "VYARM_PM remove: before clock unprepare\\n");'
new=new.replace(mark,'''\tif (vyarm_test_av1_remove_pulse) {
		int ret = vyarm_test_av1_pulse(vpu);

		if (ret)
			dev_err(vpu->dev, "VYARM_PULSE failed: %d\\n", ret);
	}
'''+mark,1)
new=new.replace('if (vyarm_test_reset(vpu, true, vpu->vyarm_test_split_resets ?', 'if (!vyarm_test_av1_remove_pulse &&\n\t    vyarm_test_reset(vpu, true, vpu->vyarm_test_split_resets ?',1)
p.write_text(new)
repo=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/worktrees/kiosk-profile-f/experiments/kiosk-f/av1-reset-research-20260922')
(repo/'hantro-powered-core-pulse-diagnostic.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/drivers/media/platform/verisilicon/hantro_drv.c',tofile='b/drivers/media/platform/verisilicon/hantro_drv.c')))
print(out)
