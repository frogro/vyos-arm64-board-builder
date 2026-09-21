#!/bin/sh
set -eu
cd /build/ffmpeg
python3 - <<'PY'
from pathlib import Path
p=Path('libavcodec/rkmppenc.c');s=p.read_text()
s=s.replace('        r->mapi->reset(r->mctx);\n        mpp_destroy(r->mctx);','        av_log(avctx, AV_LOG_WARNING, "TRACE before reset\\n");\n        r->mapi->reset(r->mctx);\n        av_log(avctx, AV_LOG_WARNING, "TRACE before destroy\\n");\n        mpp_destroy(r->mctx);\n        av_log(avctx, AV_LOG_WARNING, "TRACE after destroy\\n");')
s=s.replace('    clear_frame_list(&r->frame_list);','    av_log(avctx, AV_LOG_WARNING, "TRACE before frame cleanup\\n");\n    clear_frame_list(&r->frame_list);\n    av_log(avctx, AV_LOG_WARNING, "TRACE after frame cleanup\\n");')
p.write_text(s)
PY
make -j1 libavcodec/libavcodec.a
cp libavcodec/libavcodec.a /opt/ffmpeg/lib/
export PKG_CONFIG_PATH=/opt/ffmpeg/lib/pkgconfig:/opt/mpp/lib/pkgconfig
cc -Wall -Wextra -O2 /probe/probe.c -o /probe/encode-trace $(pkg-config --cflags --libs --static libavcodec libavutil)
