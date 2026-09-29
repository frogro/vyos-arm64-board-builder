#!/bin/bash
set -euo pipefail
cd /inputs
apt-get update -qq
apt-get install -y --no-install-recommends python3-xmltodict libpcre3
lib=$(find /inputs -maxdepth 1 -name 'libvyosconfig0_*arm64.deb' | head -1)
dpkg-deb -x "$lib" /
base=$(find /artifacts -maxdepth 1 -name 'vyos-1x_*arm64.deb' | head -1)
rm -rf /inputs/pkg
mkdir -p /inputs/pkg /inputs/output /inputs/generated
dpkg-deb -R "$base" /inputs/pkg
python3 scripts/build-command-templates build/interface-definitions/container.xml schema/interface_definition.rng generated
python3 python/vyos/xml_ref/generate_cache.py --xml-dir build/interface-definitions --internal-cache /inputs/reftree.cache --output-path /inputs
cp -a generated/container/. pkg/opt/vyatta/share/vyatta-cfg/templates/container/
cache=$(find pkg/usr/lib/python3 -name vyos_1x_cache.py)
test -n "$cache"
cp vyos_1x_cache.py "$cache"
ref=$(find pkg -name reftree.cache)
test -n "$ref"
while IFS= read -r path; do cp reftree.cache "$path"; done <<< "$ref"
py=$(dirname "$(dirname "$cache")")
cp python/vyos/kiosk.py python/vyos/kiosk_remote.py "$(dirname "$py")/"
version=$(sed -n 's/^Version: //p' pkg/DEBIAN/control)
sed -i "s/^Version: .*/Version: ${version}+wayland.20260923/" pkg/DEBIAN/control
(cd pkg; find . -type f ! -path './DEBIAN/*' -print0 | sort -z | xargs -0 md5sum | sed 's@  ./@  @' > DEBIAN/md5sums)
dpkg-deb --build --root-owner-group pkg "output/vyos-1x_${version}+wayland.20260923_arm64.deb"
chown -R 1000:1000 output
printf 'complete\n' > status
