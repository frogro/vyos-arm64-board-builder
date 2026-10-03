#!/bin/bash
# Native ARM64, isolated CI runner. Reuse only checksummed userspace inputs.
set -euo pipefail
[[ $(uname -m) == aarch64 ]]
case "$BOARD" in
 raspberry-pi-5) exec bash "$(dirname "$0")/pi5-adfg-runtime.sh" ;;
 rock-5b|orangepi5-plus) ;; *) exit 1 ;; esac
KIOSK_F=${KIOSK_F:-no}
RECEIVER_G=${RECEIVER_G:-no}
KVM_OVER_IP=${KVM_OVER_IP:-false}
[[ "$KIOSK_F" == yes || "$RECEIVER_G" == yes ]]
cd /work
mkdir inputs
assets=(runtime-kernel-inputs.tar.gz cli-builder.tar.gz)
[[ "$KIOSK_F" != yes ]] || assets+=(sunshine-source.tar.gz)
for asset in "${assets[@]}"; do
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
if [[ "$KIOSK_F" == yes ]]; then
    bash repo/experiments/kiosk-f/ci/build-runtime.sh
else
    docker load -i runtime-artifacts/runtime.tar
fi
if [[ "$RECEIVER_G" == yes ]]; then
base=$(python3 -c 'import json; print(json.load(open("runtime-artifacts/runtime.json"))["image_id"])')
base_tag=localhost/vyarm-graphics:verified-${GITHUB_RUN_ID}
docker tag "$base" "$base_tag-input"
python3 repo/tools/ci/receiver-graphics-base.py "$base_tag-input" "$base_tag"
CONTAINER_ENGINE=docker bash repo/experiments/profile-g/build-runtime.sh "$base_tag" /work/receiver-artifacts
tag=$(python3 -c 'import json; print(json.load(open("receiver-artifacts/runtime.json"))["tag"])')
docker run --rm --network none --entrypoint /bin/sh "$tag" -ec 'QT_QPA_PLATFORM=offscreen moonlight --help >/dev/null; LD_LIBRARY_PATH=/opt/ffmpeg-request/lib /opt/ffmpeg-request/bin/ffmpeg -hide_banner -hwaccels | grep -x v4l2request; gst-inspect-1.0 waylandsink >/dev/null'
docker run --rm --network none --user kiosk --entrypoint python3 "$tag" -c 'import sys; sys.path.insert(0,"/opt/profile-g"); import steamlink; steamlink.check_runtime()'
(cd receiver-artifacts && sha256sum runtime.tar runtime.json image.json > SHA256SUMS)
fi
if [[ "$KVM_OVER_IP" == true || "$KVM_OVER_IP" == yes ]]; then
# Same native runner toolchain used by the established ROCK image build.
sudo apt-get install -y libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev
gcc -Wall -Wextra -Werror -O2 repo/experiments/kiosk-f/cpu-conversion-proof/cached-launch.c $(pkg-config --cflags --libs gstreamer-video-1.0) -o cached-launch
fi
# Keep CLI build image; discard intermediate compilation layers before assembly.
docker builder prune -af
