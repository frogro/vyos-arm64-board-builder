# Official Chrome ARM64 comparison

2026-09-21. Isolated container on the same ROCK test3 kernel and Weston16
runtime as Chromium153. Production X11 kiosk unchanged. Official Google
Chrome stable ARM64 Debian package downloaded over HTTPS from:
https://dl.google.com/linux/direct/google-chrome-stable_current_arm64.deb

The mutable download URL must not be used as a reproducible version pin:
record and verify package-info.txt and package.sha256 before rebuilding.
No vendor binary is committed. Package installed into a disposable image
based on localhost/vyarm-kiosk:weston16-test3, not into the host/production.

Harness: copy ../browser-device-probe.py, ../probe-wayland.sh and
../test-browser-performance.sh into an isolated tools directory. Change
only the executable `exec chromium "$@"` to `exec google-chrome-stable "$@"`
in the probe. Same enabled features, normal sandbox, network-none container,
1080p60, GL headless Weston, same V4L2/GPU nodes and synthetic fixtures.
Run PERF_RUNS=1 for original B-pyramid + HEVC and no-pyramid + same HEVC.
Decode backend must be inspected before comparing performance. Software
playback does not establish a V4L2 solution. Browser versions differ in
patch level/build flags, so this is not a one-source-change comparison.

## Results

Official Chrome 153.0.8010.52-1 ARM64 versus previous Chromium153.0.8010.47.
Image ID: ee9ee294150b65254230b2824a9390156e8b3ab8fad31a972f422dff8c3e395f.
Mesa EGL/GBM/DRI remains25.0.7-2+deb13u1, Waylandclient1.23.1-3.

| Fixture | Chrome decoder | HTML dropped / total |
| --- | --- | --- |
| H264 B3 pyramid | FFmpegVideoDecoder, platform=false |15/1800|
| H264 B3 no pyramid | FFmpegVideoDecoder, platform=false |10/1800|
| HEVC control, both trials | Unsupported, play-error |not applicable|
| H264 pyramid verbose diagnostic repeat | FFmpegVideoDecoder, platform=false |10/1800|

SystemInfo videoDecoding profiles are empty. Diagnostic stderr contains
`media/gpu/vaapi/vaapi_wrapper.cc:1801: vaInitialize failed: unknown libva error`.
No successful V4L2 decoder is reported. GPU rendering nevertheless uses
ANGLE/Mali-G610(Panfrost); GPU rendering is not video hardware decoding.
These results establish a software control, NOT a fix for the hardware
B-pyramid path. They do not establish that all Chrome builds lack V4L2.
H265 remains unsupported in this particular official-package configuration.
Normal sandbox retained; no production package/config/driver changed.
Result JSON is reduced to page totals, decoder properties, flags and support;
frame-by-frame data, screenshots and full logs remain in live test artifacts.
