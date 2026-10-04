#!/bin/bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=$(realpath -m "${1:?Artifact directory required}")
engine=${CONTAINER_ENGINE:-docker}
commit=$(git -C "$root" rev-parse HEAD)
tag="localhost/vyarm-signage:i-${commit:0:12}"
redis_tag='localhost/vyarm-signage-redis:22448b474134'
redis_source='ghcr.io/screenly/anthias-redis@sha256:22448b47413419bbd046f3a111a17c0e03869012d988d89f0cda9f102d42d9fb'
mkdir -p "$out"
"$engine" build --platform linux/arm64 --build-arg SOURCE_REVISION="$commit" -f "$root/experiments/profile-i/container/Containerfile" -t "$tag" "$root/experiments/profile-i"
"$engine" pull --platform linux/arm64 "$redis_source"
"$engine" tag "$redis_source" "$redis_tag"
"$engine" image inspect "$tag" "$redis_tag" > "$out/image.json"
"$engine" run --rm --network none --entrypoint python "$tag" -c 'import i_profile, storage_guard, backup_limits; import importlib.metadata as m; print(m.version("Django"))'
"$engine" run --rm --network none --entrypoint redis-server "$redis_tag" --version
"$engine" save -o "$out/runtime.tar" "$tag" "$redis_tag"
python3 - "$out" "$tag" "$redis_tag" "$commit" <<'PY'
import hashlib,json,sys
from pathlib import Path
out=Path(sys.argv[1]);info=json.loads((out/'image.json').read_text())
assert len(info)==2 and all(i['Architecture']=='arm64' for i in info)
with (out/'runtime.tar').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(out/'runtime.json').write_text(json.dumps(dict(schema=1,profile='signage-i',tag=sys.argv[2],redis_tag=sys.argv[3],source_commit=sys.argv[4],archive_sha256=digest,images=[{'tag':sys.argv[n+2],'id':item['Id']} for n,item in enumerate(info)]),indent=2)+'\n')
PY
(cd "$out" && sha256sum runtime.tar runtime.json image.json > SHA256SUMS)
