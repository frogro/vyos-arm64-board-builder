from pathlib import Path
import shutil,difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-timeout-cli-20260922')
out=base/'module-errors'
shutil.copytree(base/'module',out)
p=out/'drivers/media/platform/verisilicon/rockchip_vpu981_hw_av1_dec.c';old=p.read_text();s=old
s=s.replace('prepare_error:\n\thantro_end_prepare_run(ctx);\n\thantro_irq_done(vpu, VB2_BUF_STATE_ERROR);', 'prepare_error:\n\t/* device_run owns error completion and PM/clock unwinding. */\n\thantro_end_prepare_run(ctx);',1)
anchor='\thantro_start_prepare_run(ctx);'
s=s.replace(anchor,anchor+'''\n\tif (xchg(&vyarm_test_av1_prepare_error, 0)) {
		dev_info(vpu->dev, "VYARM_PREPARE: injected preparation error\\n");
		ret = -EIO;
		goto prepare_error;
	}
''',1)
pos=s.index('\n',s.index('#include "hantro'))
s=s[:pos+1]+'''\nstatic int vyarm_test_av1_prepare_error;
module_param(vyarm_test_av1_prepare_error, int, 0644);
MODULE_PARM_DESC(vyarm_test_av1_prepare_error, "TEST ONLY: fail one AV1 preparation before starting hardware");
'''+s[pos+1:]
p.write_text(s)
Path(__file__).with_name('hantro-av1-single-error-completion-diagnostic.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='a/drivers/media/platform/verisilicon/rockchip_vpu981_hw_av1_dec.c',tofile='b/drivers/media/platform/verisilicon/rockchip_vpu981_hw_av1_dec.c')))
