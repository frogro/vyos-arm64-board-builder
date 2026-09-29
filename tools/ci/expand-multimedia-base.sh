#!/bin/bash
# Expand only the downloaded disposable raw file, never a physical device.
set -euo pipefail
raw=$(realpath "${1:?Raw file required}")
[[ -f "$raw" && ! -b "$raw" && "$raw" == */work/raw-artifact/* ]]
loop=$(losetup --find --show --read-only --partscan "$raw")
trap '[[ -z "$loop" ]] || losetup -d "$loop"' EXIT
udevadm settle
number=
for part in "${loop}"p*; do
    [[ -b "$part" ]] || continue
    if [[ $(blkid -s LABEL -o value "$part") == persistence && $(blkid -s TYPE -o value "$part") == ext4 ]]; then
        [[ -z "$number" ]]
        number=${part##*p}
    fi
done
[[ $number =~ ^[0-9]+$ ]]
losetup -d "$loop"; loop=
# Require persistence to be the last partition; never erase following data.
python3 - "$raw" "$number" <<'PY'
import json,subprocess,sys
parts=json.loads(subprocess.check_output(['sfdisk','--json',sys.argv[1]]))['partitiontable']['partitions']
last=max(parts,key=lambda p:p['start'])
assert last['node']==sys.argv[1]+sys.argv[2] or last['node']==sys.argv[1]+'p'+sys.argv[2],last
PY
[[ $(stat -c %s "$raw") -le 17179869184 ]]
truncate -s 16G "$raw"
sgdisk -e "$raw"
start=$(sgdisk -i "$number" "$raw" | awk '/First sector:/ {print $3}')
[[ $start =~ ^[0-9]+$ ]]
sgdisk -d "$number" -n "${number}:${start}:0" -t "${number}:8300" -c "${number}:persistence" "$raw"
loop=$(losetup --find --show --partscan "$raw")
udevadm settle
e2fsck -pf "${loop}p${number}" || [[ $? == 1 ]]
resize2fs "${loop}p${number}"
