#!/bin/bash
set -euo pipefail
cd /work
S=repo/experiments/kiosk-f/sunshine
mkdir sunshine-build-context runtime-next
cp inputs/sunshine-source.tar.gz sunshine-build-context/
cp "$S/kms-timing/Containerfile" "$S/kms-timing/0001-kms-stage-timing.patch" "$S/0002-mpp-container-compatible-path.patch" "$S/hevc/"*.patch "$S/rga-converter/0001-opt-in-sunshine-converter.patch" "$S/rga-converter/rga-converter.hpp" sunshine-build-context/
docker build --platform linux/arm64 --network host -t localhost/vyarm-sunshine-build:kms-timing-20260927 -f sunshine-build-context/Containerfile sunshine-build-context 2>&1 | tee /work/sunshine-build.log
BASE_ID=$(python3 -c 'import json; print(json.load(open("runtime-artifacts/runtime.json"))["image_id"])')
docker load -i runtime-artifacts/runtime.tar
# BuildKit resolves a bare sha256 image ID as a registry name in FROM.
# Verify the imported content before assigning a local, run-specific tag.
test "$(docker image inspect --format '{{.Id}}' "$BASE_ID")" = "$BASE_ID"
BASE=localhost/vyarm-kiosk-base:verified-${GITHUB_RUN_ID}
docker tag "$BASE_ID" "$BASE"
test "$(docker image inspect --format '{{.Id}}' "$BASE")" = "$BASE_ID"
mkdir runtime-next/helpers
cp repo/experiments/kiosk-f/container/kiosk-*.py repo/experiments/kiosk-f/container/start-kiosk runtime-next/helpers/
TAG=localhost/vyarm-kiosk:github-${GITHUB_RUN_ID}
docker build --platform linux/arm64 --network none --build-arg BASE_IMAGE="$BASE" --build-arg SOURCE_REVISION="$GITHUB_SHA" -t "$TAG" -f repo/experiments/kiosk-f/ci/Containerfile.runtime-next runtime-next
docker image inspect "$TAG" > runtime-next/inspect.json
docker run --rm --network none --entrypoint sha256sum "$TAG" /usr/bin/sunshine /opt/vyarm/chromium/chrome > runtime-next/binary-hashes.txt
docker save "$TAG" -o runtime-next/runtime.tar
python3 - <<'PY'
import hashlib,json,pathlib,os,shutil
p=pathlib.Path('/work');meta=json.loads((p/'runtime-artifacts/runtime.json').read_text());i=json.loads((p/'runtime-next/inspect.json').read_text())[0]
archive=p/'runtime-next/runtime.tar'
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
meta.update(image=i['RepoTags'][0],image_id=i['Id'],archive_sha256=digest,builder_commit=os.environ['GITHUB_SHA'],sunshine_instrumentation=True,binary_hashes=(p/'runtime-next/binary-hashes.txt').read_text())
shutil.move(archive,p/'runtime-artifacts/runtime.tar');(p/'runtime-artifacts/runtime.json').write_text(json.dumps(meta,indent=2)+'\n')
PY
