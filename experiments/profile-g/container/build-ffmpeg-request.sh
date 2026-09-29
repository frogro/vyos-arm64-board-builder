#!/bin/bash
# Private, pinned diagnostic FFmpeg; never replaces distro/GStreamer libraries.
set -euo pipefail
revision=904a85173fab816bb3c30652300efa93f2333657
git init /src/ffmpeg-request
cd /src/ffmpeg-request
git remote add origin https://github.com/jernejsk/FFmpeg.git
git fetch --depth=1 origin "$revision"
git checkout --detach FETCH_HEAD
test "$(git rev-parse HEAD)" = "$revision"
git apply --check /tmp/ffmpeg-rps/0002-exact-7.1-backport.patch
git apply /tmp/ffmpeg-rps/0002-exact-7.1-backport.patch
install -m644 /tmp/ffmpeg-rps/v4l2-hevc-rps-compat.h libavcodec/v4l2-hevc-rps-compat.h
./configure --prefix=/opt/ffmpeg-request --enable-shared --disable-static \
 --disable-doc --disable-debug --disable-autodetect --enable-libdrm \
 --enable-v4l2-request --disable-everything --enable-avcodec \
 --enable-avutil --enable-swscale --enable-avformat --enable-swresample \
 --enable-decoder=h264,hevc,aac --enable-parser=h264,hevc,aac \
 --enable-hwaccel=h264_v4l2request,hevc_v4l2request \
 --enable-demuxer=mpegts,h264,hevc,mov --enable-protocol=file \
 --enable-muxer=null --enable-encoder=wrapped_avframe \
 --enable-filter=null,anull --enable-ffmpeg
make -j2
make DESTDIR=/request-out install
install -m644 /dev/null /request-out/opt/ffmpeg-request/source-commit.txt
printf '%s\n' "$revision" > /request-out/opt/ffmpeg-request/source-commit.txt
LD_LIBRARY_PATH=/request-out/opt/ffmpeg-request/lib \
 /request-out/opt/ffmpeg-request/bin/ffmpeg -hide_banner -hwaccels | grep -x v4l2request

cp -r /tmp/ffmpeg-rps /request-out/opt/ffmpeg-request/patches
