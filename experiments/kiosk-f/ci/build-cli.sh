#!/bin/bash
set -euo pipefail
cd /work
[[ $(uname -m) == aarch64 ]]
git init cli-source
git -C cli-source remote add origin https://github.com/vyos/vyos-1x.git
git -C cli-source fetch --depth 1 origin 4e3e38a2e665bb2d8e9446116e02300bb38a2ab4
git -C cli-source checkout --detach FETCH_HEAD
python3 repo/tools/prepare-vyos-1x-profile.py cli-source --version 999.0-14942-g4e3e38a2e --kvm --tailscale --kiosk
python3 - <<'PY'
import json
m=json.load(open('cli-source/data/arm64-profile-source.json'))
assert m['recipe_sha256']=='f7a18d9dddcaef2028f969fb271062918e4a8e20b13e071d38f297db95c738fd',m
PY
git -C cli-source add .
docker image inspect -f '{{.Id}}' vyos-profile-build:arm64-22dfa15927f2 > build-image-id.txt
mkdir package-tmp
echo building > cli-status
docker run --rm --privileged --network host --platform linux/arm64 --memory=8g --cpus=4 -v /work:/work -v /work/package-tmp:/tmp -w /work/cli-source -e DEB_BUILD_OPTIONS=parallel=4 --entrypoint /bin/bash vyos-profile-build:arm64-22dfa15927f2 -lc 'git config --global --add safe.directory /work/cli-source; dpkg-buildpackage -b -us -uc' 2>&1 | tee cli-build.log
echo complete > cli-status
python3 finalize-cli.py
