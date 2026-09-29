#!/bin/bash
# Native ARM64, isolated CI runner. Reuse only checksummed userspace inputs.
set -euo pipefail
[[ $(uname -m) == aarch64 ]]
case "$BOARD" in rock-5b|orangepi5-plus) ;; *) exit 1 ;; esac
cd /work
mkdir inputs
for asset in runtime-kernel-inputs.tar.gz sunshine-source.tar.gz cli-builder.tar.gz; do
    gh release download adf-compare-inputs-20260927 --repo "$GITHUB_REPOSITORY" --dir inputs --pattern "$asset"
    expected=$(awk -v name="$asset" '$2==name {print $1}' repo/experiments/kiosk-f/ci/inputs.sha256)
    [[ $expected =~ ^[0-9a-f]{64}$ ]]
    echo "$expected  inputs/$asset" | sha256sum -c -
done
# Do not extract ROCK kernel, modules, DTBs or firmware artifacts.
tar -xzf inputs/runtime-kernel-inputs.tar.gz --wildcards --no-anchored 'runtime-artifacts/*'
rm inputs/runtime-kernel-inputs.tar.gz
python3 - <<'PY'
import hashlib,json,pathlib
p=pathlib.Path('runtime-artifacts');m=json.loads((p/'runtime.json').read_text())
with (p/'runtime.tar').open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==m['archive_sha256']
PY
docker load -i inputs/cli-builder.tar.gz
rm inputs/cli-builder.tar.gz
test "$(docker image inspect --format '{{.Architecture}}' vyos-profile-build:arm64-22dfa15927f2)" = arm64
bash repo/experiments/kiosk-f/ci/build-runtime.sh
CONTAINER_ENGINE=docker bash repo/experiments/profile-g/build-runtime.sh "localhost/vyarm-kiosk:github-${GITHUB_RUN_ID}" /work/receiver-artifacts
tag=$(python3 -c 'import json; print(json.load(open("receiver-artifacts/runtime.json"))["tag"])')
docker run --rm --network none --entrypoint /bin/sh "$tag" -ec 'QT_QPA_PLATFORM=offscreen moonlight --help >/dev/null; LD_LIBRARY_PATH=/opt/ffmpeg-request/lib /opt/ffmpeg-request/bin/ffmpeg -hide_banner -hwaccels | grep -x v4l2request; gst-inspect-1.0 waylandsink >/dev/null'
docker run --rm --network none --user kiosk --entrypoint python3 "$tag" -c 'import sys; sys.path.insert(0,"/opt/profile-g"); import steamlink; steamlink.check_runtime()'
# Same native runner toolchain used by the established ROCK image build.
sudo apt-get install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
gcc -Wall -Wextra -Werror -O2 repo/experiments/kiosk-f/cpu-conversion-proof/cached-launch.c $(pkg-config --cflags --libs gstreamer-video-1.0) -o cached-launch
(cd receiver-artifacts && sha256sum runtime.tar runtime.json image.json > SHA256SUMS)
# Keep CLI build image; discard intermediate compilation layers before assembly.
docker builder prune -af
