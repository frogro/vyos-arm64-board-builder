from pathlib import Path
import shutil,difflib
base=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp')
src=base/'av1-reset-research-20260922/pulse-candidate'
out=base/'av1-timeout-cli-20260922/module'
out.mkdir(parents=True,exist_ok=False)
shutil.copytree(src/'drivers',out/'drivers')
(out/'Makefile').write_text('obj-m += drivers/media/platform/verisilicon/\n')
p=out/'drivers/media/platform/verisilicon/hantro_drv.c';old=p.read_text();s=old
s=s.replace('int i, ret;\n\n\tif (!vpu->vyarm_test_split_resets)', 'int i, ret, first_error = 0;\n\n\tif (!vpu->vyarm_test_split_resets)',1)
s=s.replace('\t\tif (ret)\n\t\t\treturn ret;\n\t}\n\treturn 0;\n}', '\t\tif (ret && !first_error)\n\t\t\tfirst_error = ret;\n\t}\n\treturn first_error;\n}',1)
s=s.replace('int ret, deassert_ret;', 'int ret, deassert_ret, pm_ret;',1)
s=s.replace('\tpm_runtime_put_sync_suspend(vpu->dev);\n\treturn ret;', '\tpm_ret = pm_runtime_put_sync_suspend(vpu->dev);\n\treturn ret ? ret : (pm_ret < 0 ? pm_ret : 0);',1)
validation='\tif (vyarm_test_av1_remove_pulse &&\n\t    (!vpu->vyarm_test_split_resets || vyarm_test_remove_reset_mask != 3))\n\t\treturn -EINVAL;\n\n'
s=s.replace(validation,'',1)
s=s.replace('\tif (vpu->variant->init) {',validation+'\tif (vpu->variant->init) {',1)
# One acknowledged completion is withheld; watchdog owns the job. No IRQ line disabled.
s=s.replace('int hantro_debug;', '''static int vyarm_test_drop_av1_completion;
module_param(vyarm_test_drop_av1_completion, int, 0644);
MODULE_PARM_DESC(vyarm_test_drop_av1_completion, "TEST ONLY: consume one AV1 completion to exercise watchdog");

int hantro_debug;''',1)
s=s.replace('\t/*\n\t * If cancel_delayed_work', '''\tif (ctx && vpu->variant->codec == HANTRO_AV1_DECODER &&
	    vyarm_test_av1_remove_pulse &&
	    xchg(&vyarm_test_drop_av1_completion, 0)) {
		dev_info(vpu->dev, "VYARM_TIMEOUT: acknowledged completion withheld\\n");
		return;
	}

	/*
	 * If cancel_delayed_work''',1)
s=s.replace('\t\tif (ctx->codec_ops->reset)\n', '''\t\tif (vpu->variant->codec == HANTRO_AV1_DECODER &&
		    vyarm_test_av1_remove_pulse) {
			int ret = vyarm_test_av1_pulse(vpu);

			dev_info(vpu->dev, "VYARM_TIMEOUT: powered recovery returned %d\\n", ret);
		}
		if (ctx->codec_ops->reset)
''',1)
s=s.replace('ret = clk_bulk_enable(ctx->dev->variant->num_clocks, ctx->dev->clocks);\n\tif (ret)\n\t\tgoto err_cancel_job;', 'ret = clk_bulk_enable(ctx->dev->variant->num_clocks, ctx->dev->clocks);\n\tif (ret)\n\t\tgoto err_put_pm;',1)
s=s.replace('if (ctx->codec_ops->run(ctx))\n\t\tgoto err_cancel_job;', 'if (ctx->codec_ops->run(ctx))\n\t\tgoto err_disable_clocks;',1)
s=s.replace('err_cancel_job:\n\thantro_job_finish_no_pm', '''err_disable_clocks:
	cancel_delayed_work_sync(&ctx->dev->watchdog_work);
	clk_bulk_disable(ctx->dev->variant->num_clocks, ctx->dev->clocks);
err_put_pm:
	pm_runtime_put_autosuspend(ctx->dev->dev);
err_cancel_job:
	hantro_job_finish_no_pm''',1)
assert s!=old;p.write_text(s)
Path(__file__).with_name('hantro-timeout-hardening-diagnostic.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),s.splitlines(True),fromfile='a/drivers/media/platform/verisilicon/hantro_drv.c',tofile='b/drivers/media/platform/verisilicon/hantro_drv.c')))
print(out)
