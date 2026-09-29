#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates devscripts equivs
apt-get build-dep -y /src
cd /src
cat > /tmp/vyarm-build.mk <<'EOF'
defines := $(filter-out use_thin_lto=true,$(defines)) use_thin_lto=false concurrent_links=1
.PHONY: vyarm-gn
vyarm-gn: override_dh_auto_configure
	gn gen out/Release --threads=1 --args="$(defines)"
EOF
DEB_BUILD_OPTIONS=parallel=1 make -f debian/rules -f /tmp/vyarm-build.mk vyarm-gn
ninja -C out/Release -t targets all > /src/vyarm-targets.txt
python3 - <<'PY' > /tmp/target
from pathlib import Path
matches=[s.split(':',1)[0] for s in Path('/src/vyarm-targets.txt').read_text().splitlines() if '/v4l2_video_decoder_backend_stateless.o:' in s or '/v4l2_video_decoder.o:' in s]
assert len(matches)==2,matches
print('\n'.join(matches))
PY
xargs -a /tmp/target ninja -j1 -C out/Release
printf '\nVYARM_BOTH_OBJECTS_COMPILED\n'
