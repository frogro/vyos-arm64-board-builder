#!/bin/bash
set -euo pipefail
cd /src
exec > >(tee /src/vyarm-lowdelay-incremental.log) 2>&1
trap 'rc=$?; echo "$rc" > /src/vyarm-lowdelay-incremental.exit; date -u; exit "$rc"' EXIT
printf '%s  %s\n' 3cfa5afeb54336f14dab402cbe3e289d21e53df34d8172f2bc0a8d8defc86a55 media/gpu/chromeos/video_decoder_pipeline.cc | sha256sum -c -
mkdir /src/baseline-av1-20260922
cp --reflink=auto out/Release/chrome out/Release/chrome_sandbox out/Release/args.gn source-files.sha256 media/gpu/chromeos/video_decoder_pipeline.cc /src/baseline-av1-20260922/
sha256sum out/Release/chrome > /src/baseline-av1-20260922/browser.sha256
cp /src/vyarm-pipeline-candidate.cc media/gpu/chromeos/video_decoder_pipeline.cc
python3 - <<'MANIFEST'
import hashlib,pathlib
p=pathlib.Path('source-files.sha256');lines=p.read_text().splitlines();name='media/gpu/chromeos/video_decoder_pipeline.cc'
assert sum(x.endswith('  '+name) for x in lines)==1
p.write_text('\n'.join(hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()+'  '+name if x.endswith('  '+name) else x for x in lines)+'\n')
MANIFEST
sha256sum -c source-files.sha256
export DEB_BUILD_PROFILES=cross
export DEB_BUILD_OPTIONS='parallel=8 terse'
export HOST_EXEC_WRAPPER=aarch64-linux-gnu-cross-exe-wrapper
eval "$(dpkg-architecture -aarm64 -s)"
export CXXFLAGS_FOR_BUILD='-O2'
export LDFLAGS_FOR_BUILD=''
date -u
ninja -n -C out/Release chrome chrome_sandbox > /src/vyarm-lowdelay-incremental-dry.log
wc -l /src/vyarm-lowdelay-incremental-dry.log
ninja -j8 -C out/Release chrome chrome_sandbox
sha256sum out/Release/chrome
echo VYARM_LOWDELAY_INCREMENTAL_COMPLETE
