from pathlib import Path
r=Path('/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/av1-reset-candidates-20260922')
base=Path('/tmp/av1-pulse-repeat.sh').read_text()
for label,identity,tlb,cycles in [('control','N','N','1'),('identity','Y','N','1 2 3'),('tlb','N','Y','1 2 3'),('both','Y','Y','1 2 3')]:
 s=base.replace('av1-reset-research-20260922/pulse-repeat','av1-reset-candidates-20260922/'+label).replace('vyarm-av1-pulse-repeat','vyarm-av1-candidate-'+label).replace('for cycle in 1 2 3 4 5;', 'for cycle in '+cycles+';')
 s=s.replace('bash /config/kiosk-test/kernel-test4/preflight.sh','''grep -q 'vyarm_av1_candidates=1' /proc/cmdline
bash /config/kiosk-test/kernel-test4/preflight.sh
cp /config/kiosk-test/av1-reset-candidates-20260922/watchdog.py /run/vyarm-av1-watchdog.py
p=/sys/module/vsi_iommu/parameters
printf '%s\\n' '''+identity+''' > "$p/vyarm_identity_guard"
printf '%s\\n' '''+tlb+''' > "$p/vyarm_nonsleeping_tlb"
cat "$p"/vyarm_*''')
 (r/('test-'+label+'.sh')).write_text(s)
