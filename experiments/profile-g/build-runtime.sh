#!/bin/bash
# Native ARM64 build; BASE is an already available, validated F runtime image.
set -euo pipefail
base=${1:?Usage: build-runtime.sh <local-tested-F-image> <new-output-directory>}
out=${2:?Output directory required}
root=$(cd "$(dirname "$0")/../.." && pwd)
[[ -z $(git -C "$root" status --porcelain) ]] || { echo 'Commit source changes before building' >&2; exit 1; }
engine=${CONTAINER_ENGINE:-podman}
[[ "$engine" == podman || "$engine" == docker ]] || exit 1
[[ $(uname -m) == aarch64 ]] || { echo 'Use a native ARM64 build host' >&2; exit 1; }
[[ ! -e "$out" ]] || { echo 'Output must be new; existing artifacts are preserved' >&2; exit 1; }
[[ $($engine image inspect --format '{{.Architecture}}' "$base") == arm64 ]]
id=$($engine image inspect --format '{{.Id}}' "$base")
# Named local tag: BuildKit interprets a bare sha256 ID as a registry name.
base_tag=localhost/vyarm-g-base:${id#sha256:}
$engine tag "$base" "$base_tag"
mkdir -p "$out"
out=$(realpath "$out")
tag=localhost/vyarm-receiver:g-$(git -C "$root" rev-parse --short HEAD)
$engine build --network=host --build-arg "BASE_IMAGE=$base_tag" -f "$root/experiments/profile-g/container/Containerfile" -t "$tag" "$root" 2>&1 | tee "$out/build.log"
$engine save -o "$out/runtime.tar" "$tag"
$engine image inspect "$tag" > "$out/image.json"
python3 - "$out" "$tag" "$id" "$root" <<'PY'
import hashlib,json,subprocess,sys
from pathlib import Path
out=Path(sys.argv[1])
with (out/'runtime.tar').open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
(out/'runtime.json').write_text(json.dumps({'schema':1,'profile':'receiver-g','tag':sys.argv[2], 'base_image_id':sys.argv[3], 'source_commit':subprocess.check_output(['git','-C',sys.argv[4],'rev-parse','HEAD'],text=True).strip(),'archive_sha256':digest},indent=2)+'\n')
PY
