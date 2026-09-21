#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
test ! -e 'weston16.tar.gz'
curl -fLsS 'https://codeload.github.com/wayland-mirror/weston/tar.gz/refs/tags/16.0.0' -o 'weston16.tar.gz'
printf '%s\n' '6a81af51045ccb2813f3a1d63ff8a66c121743c1a5ff3ce78388660bf650c55c  weston16.tar.gz' | sha256sum -c -
test ! -e 'protocols.tar.gz'
curl -fLsS 'https://codeload.github.com/wayland-mirror/wayland-protocols/tar.gz/refs/tags/1.46' -o 'protocols.tar.gz'
printf '%s\n' '83afedde1e63751578ba51b5f6c36052802f85634ed68be41ecfcc3a515ab03d  protocols.tar.gz' | sha256sum -c -
