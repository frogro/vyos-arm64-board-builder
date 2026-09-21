# VP9 / AV1 capability probe

2026-09-21, stock Chromium153.0.8010.47 on isolated Weston16/test3.
Two synthetic 5-second 1920x1080@60, 8-bit420, 8Mbps target clips (300frames).
This is a capability/startup check, NOT a long performance or visual-quality
qualification and not comparable with the 30second H264/HEVC drop totals.

| Codec | Actual decoder | Hardware flag | Result |
|---|---|---|---|
|VP9|VpxVideoDecoder|false|ended300frames,8HTMLdrops|
|AV1|Dav1dVideoDecoder|false|ended300frames,12HTMLdrops|

Current /dev/video2 advertises only parsed H264/HEVC. This describes the
running kernel/driver, not all capabilities of the SoC silicon. No VP9/AV1
hardwarepath proved. Software playback works; power/CPU/thermal impact and
longer streams require separate tests. No changes to D/F defaults.

Fixtures generated locally with FFmpeg (2encoderthreads/parallelism):
```
ffmpeg -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 5 -an -c:v libvpx-vp9 -deadline realtime -cpu-used 8 -threads 2 -b:v 8M -pix_fmt yuv420p test-vp9.webm
ffmpeg -f lavfi -i testsrc2=size=1920x1080:rate=60 -t 5 -an -c:v libsvtav1 -preset 12 -svtav1-params lp=2 -b:v 8M -pix_fmt yuv420p test-av1.webm
```
SVT2.3 mapped preset12 to11 (recorded encoder message). Copy existing browser
probe harness to tools/, replace performance script codec list with(vp9 av1),
use included HTML and WebM fixtures. Run run.sh after validating decoder nodes.
Retain sandbox, network-none, memory1GiB. Legacy `support` query in original
probe covers H264/HEVC only and was omitted from reduced results here; actual
media events establish codec/backend. No vendor binaries committed.
