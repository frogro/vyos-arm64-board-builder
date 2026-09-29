# Isolated browser pacing flags, 2026-09-21

Same Chromium153, Weston16 image, baseline1800frame1080p60 fixtures and
V4L2 decoder. Production unchanged. Run test-browser-performance.sh with
PERF_RUNS=1 and PERF_PACING=unlimited. For single-flag comparisons copy
browser-device-probe.py and retain only the named flag in the unlimited
branch. Normal control runs last with PERF_PACING=default.

| Flags | H264 pyramid | HEVC |
|---|---|---|
|disable-gpu-vsync + disable-frame-rate-limit|timeout|timeout|
|disable-gpu-vsync only|ended257drops|ended10drops|
|disable-frame-rate-limit only|timeout|timeout|
|normal control|ended270drops|ended35drops|

Combined flags with no-pyramid H264: ended1390/1800drops. PairedHEVC did
not reachEOS (last captured stateplaying). All these are presentation
observations, not networkpacketloss. Do not treat playing state as pass.
The timeouts do not demonstrate a kerneldeadlock: later normalcontrol
completed. Neither flag combination solves the pyramid case. One trial
pervariant, not statisticalproof or physicalHDMIvalidation. Hardware
selection is recorded in reducedJSON; no CPUfallback was selected.
