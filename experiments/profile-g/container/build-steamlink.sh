#!/bin/bash
# ARM64 only. Pin the official Valve payload; no updater/host udev installation.
set -euo pipefail
version=1.3.32.316
archive=32f737f0167727bff739a5b793b87222b603ec0da7837991a493e7a81e77bb62
shell=b245adfccc2cda43e405194cd66615c30ffdae6f7416b7db0579d5c161a3f7fd
curl --fail --location --retry 3 "https://media.steampowered.com/steamlink/rpi/trixie/arm64/steamlink-rpi-trixie-arm64-$version.tar.gz" -o /tmp/steamlink.tar.gz
echo "$archive  /tmp/steamlink.tar.gz" | sha256sum -c
mkdir -p /steam-out/opt
# Tarball is hash-pinned, not a moving download.
tar --no-same-owner -xzf /tmp/steamlink.tar.gz -C /steam-out/opt
# Valve's archive carries private 0700 modes and build-host UID 4009.
# The packaged client runs as kiosk, while its immutable files stay root-owned.
chown -R 0:0 /steam-out/opt/steamlink
chmod -R a+rX /steam-out/opt/steamlink
echo "$shell  /steam-out/opt/steamlink/bin/shell" | sha256sum -c
cc -Wall -Wextra -Werror -O2 -shared -fPIC /tmp/steamlink/ifaddrs-guard.c -ldl -pthread -o /steam-out/opt/steamlink/ifaddrs-guard.so
cc -Wall -Wextra -Werror -O2 -shared -fPIC /tmp/steamlink/request-bridge.c -I/request-out/opt/ffmpeg-request/include -ldl -o /steam-out/opt/steamlink/request-bridge.so
# Record the actual build, rather than accepting arbitrary replacement libraries.
(cd /request-out && find opt/ffmpeg-request/lib -type f -name '*.so*' -print0 | sort -z | xargs -0 sha256sum) > /steam-out/opt/steamlink/request-libs.sha256
printf '%s\n' "$version" > /steam-out/opt/steamlink/pinned-version.txt
# USB redirection is not qualified on RK3588 and must never invoke Valve's
# Raspberry-Pi host reconfiguration helper. Pairing/audio/video are unaffected.
printf '#!/bin/sh\n# Profile G: USB redirection intentionally disabled.\nexit 0\n' > /steam-out/opt/steamlink/bin/usb_sharing.sh
chmod 755 /steam-out/opt/steamlink/bin/usb_sharing.sh
