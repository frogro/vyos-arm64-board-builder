#!/usr/bin/env bash
# A separate Docker daemon: no changes to the existing Docker configuration.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run this script with sudo.' >&2; exit 1; }
BASE=/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=999.0-14891-gd185906f3
UNIT=vyos-profile-build-docker
CTR_UNIT=vyos-profile-build-containerd
[[ -x "$REPO/tools/build-vyos-1x-profile.py" ]] || exit 1
mountpoint -q /mnt/entwicklung || { echo 'Development disk is not mounted.' >&2; exit 1; }
[[ $(df --output=avail -B1 /mnt/entwicklung | tail -1) -gt 32212254720 ]] || { echo 'At least 30 GiB free required.' >&2; exit 1; }
[[ $(systemctl is-active "$UNIT" || true) != active ]] || { echo 'Build daemon already running; inspect it before starting another build.' >&2; exit 1; }
mkdir -p "$BASE" "$BASE/runs" "$BASE/files"
export TMPDIR="$BASE/files"
chmod 0755 "$BASE"
export DOCKER_HOST="unix://$BASE/docker.sock"
export VYOS_1X_ALLOW_EMULATION=yes
TASK_RUN="$BASE/runs/$(date +%Y%m%d-%H%M%S)"
mkdir "$TASK_RUN"
python3 - "$BASE" <<'PY'
import json,sys
from pathlib import Path
base=Path(sys.argv[1])
(base/'daemon.json').write_text(json.dumps({
 'data-root':str(base/'docker'), 'exec-root':str(base/'exec'),
 'pidfile':str(base/'dockerd.pid'), 'hosts':['unix://'+str(base/'docker.sock')],
 'containerd':str(base/'ctr.sock'),
 'containerd-namespace':'vyos-profile-build',
 'containerd-plugins-namespace':'vyos-profile-build-plugins',
 'bridge':'none', 'iptables':False, 'ip6tables':False, 'ip-forward':False,
 'ip-masq':False, 'storage-driver':'overlay2',
 'features':{'containerd-snapshotter':False}
},indent=2)+'\n')
PY
dockerd --validate --config-file "$BASE/daemon.json"
cat > "$BASE/containerd.toml" <<EOF
version = 3
root = "$BASE/containerd"
state = "$BASE/state"
[grpc]
  address = "$BASE/ctr.sock"
EOF
systemd-run --unit="$CTR_UNIT" --collect \
    --property="StandardOutput=append:$BASE/containerd.log" \
    --property="StandardError=append:$BASE/containerd.log" \
    /usr/bin/containerd --config "$BASE/containerd.toml"
cleanup() { systemctl stop "$UNIT" || true; systemctl stop "$CTR_UNIT" || true; }
trap cleanup EXIT
for attempt in $(seq 1 30); do
    [[ -S "$BASE/ctr.sock" ]] && break
    sleep 1
done
[[ -S "$BASE/ctr.sock" ]] || { tail -40 "$BASE/containerd.log"; exit 1; }
systemd-run --unit="$UNIT" --collect \
    --property="StandardOutput=append:$BASE/dockerd.log" \
    --property="StandardError=append:$BASE/dockerd.log" \
    /usr/bin/dockerd --config-file "$BASE/daemon.json"
ready=no
for attempt in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then ready=yes; break; fi
    sleep 1
done
[[ "$ready" == yes ]] || { tail -40 "$BASE/dockerd.log"; exit 1; }
[[ $(docker info --format '{{.DockerRootDir}}') == "$BASE/docker" ]] || exit 1
# Install ARM64 emulation for this boot. This does not change the normal daemon.
docker run --rm --privileged --network host tonistiigi/binfmt --install arm64
export REPO VERSION TASK_RUN
python3 - <<'PY' 2>&1 | tee "$TASK_RUN/build.log"
import importlib.util, os
from pathlib import Path
p=Path(os.environ['REPO'])/'tools/build-vyos-1x-profile.py'
spec=importlib.util.spec_from_file_location('builder',p)
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
builder.build(os.environ['VERSION'],Path(os.environ['TASK_RUN'])/'artifacts')
PY
printf 'Package test complete. Artifacts and log: %s\n' "$TASK_RUN"
