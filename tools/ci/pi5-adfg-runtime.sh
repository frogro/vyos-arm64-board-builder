#!/bin/bash
# A distinct Pi graphics userspace; only the shared CLI compiler is imported.
set -euo pipefail
[[ $(uname -m) == aarch64 && "$BOARD" == raspberry-pi-5 ]]
cd /work
mkdir -p inputs
gh release download adf-compare-inputs-20260927 --repo "$GITHUB_REPOSITORY" --dir inputs --pattern cli-builder.tar.gz
expected=$(awk '$2=="cli-builder.tar.gz" {print $1}' repo/experiments/kiosk-f/ci/inputs.sha256)
[[ $expected =~ ^[0-9a-f]{64}$ ]]
echo "$expected  inputs/cli-builder.tar.gz" | sha256sum -c -
docker load -i inputs/cli-builder.tar.gz
rm inputs/cli-builder.tar.gz
[[ $(docker image inspect --format '{{.Architecture}}' vyos-profile-build:arm64-22dfa15927f2) == arm64 ]]
base=localhost/vyarm-pi5-graphics:${GITHUB_RUN_ID}
docker build --target graphics -f repo/experiments/kiosk-f/container/Containerfile.pi5 -t "$base" repo
if [[ ${KIOSK_F:-no} == yes ]]; then
    tag=localhost/vyarm-kiosk:pi5-${GITHUB_RUN_ID}
    docker build --target kiosk -f repo/experiments/kiosk-f/container/Containerfile.pi5 -t "$tag" repo
    mkdir runtime-artifacts
    docker save -o runtime-artifacts/runtime.tar "$tag"
    docker image inspect "$tag" > runtime-artifacts/image.json
    python3 - "$tag" <<'PY'
import hashlib,json,pathlib,subprocess,sys
p=pathlib.Path('runtime-artifacts')
with (p/'runtime.tar').open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
meta={'schema':1,'image':sys.argv[1],'image_id':json.loads((p/'image.json').read_text())[0]['Id'],'archive_sha256':digest,'builder_commit':subprocess.check_output(['git','-C','repo','rev-parse','HEAD'],text=True).strip()}
(p/'runtime.json').write_text(json.dumps(meta,indent=2)+'\n')
PY
fi
if [[ ${RECEIVER_G:-no} == yes ]]; then
    CONTAINER_ENGINE=docker bash repo/experiments/profile-g/build-runtime.sh "$base" /work/receiver-artifacts
    tag=$(python3 -c 'import json; print(json.load(open("receiver-artifacts/runtime.json"))["tag"])')
    docker run --rm --network none --entrypoint /bin/sh "$tag" -ec 'QT_QPA_PLATFORM=offscreen moonlight --help >/dev/null; gst-inspect-1.0 waylandsink >/dev/null; gst-inspect-1.0 tsdemux >/dev/null'
    docker run --rm --network none --user kiosk --entrypoint python3 "$tag" -c 'import sys; sys.path.insert(0,"/opt/profile-g"); import steamlink; steamlink.check_runtime()'
fi
docker builder prune -af
