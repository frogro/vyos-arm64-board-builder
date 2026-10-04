#!/bin/bash
# Build a standalone ARM64 CUPS/Gutenprint image. VirtualHere is not bundled.
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
out=$(realpath -m "${1:?Artifact directory required}")
engine=${CONTAINER_ENGINE:-docker}
commit=$(git -C "$root" rev-parse HEAD)
tag="localhost/vyarm-print:e-${commit:0:12}"
mkdir -p "$out"
"$engine" build --platform linux/arm64 -f "$root/experiments/profile-e/container/Containerfile" -t "$tag" "$root/experiments/profile-e/container"
"$engine" image inspect "$tag" > "$out/image.json"
"$engine" run --rm --network none --entrypoint /bin/sh "$tag" -ec 'command -v cupsd; test -x /usr/lib/cups/backend/gutenprint53+usb; test -x /usr/lib/cups/driver/gutenprint.5.3'
"$engine" save -o "$out/runtime.tar" "$tag"
python3 - "$out" "$tag" "$commit" <<'PY'
import hashlib,json,sys
from pathlib import Path
out=Path(sys.argv[1]);info=json.loads((out/'image.json').read_text())[0]
assert info['Architecture']=='arm64'
with (out/'runtime.tar').open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
(out/'runtime.json').write_text(json.dumps(dict(schema=1,profile='print-server-e',tag=sys.argv[2],source_commit=sys.argv[3],archive_sha256=digest),indent=2)+'\n')
PY
(cd "$out" && sha256sum runtime.tar runtime.json image.json > SHA256SUMS)
