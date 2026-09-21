# SPS/RPS conformance probes, test3

FFmpeg FATE HEVC Main8bit samples,416x240. RPS_A_docomo_4:44 frames,
11 SPS short-term RPS sets. LTRPSPS_A_Qualcomm_1:500 frames,12 SPS
short-term sets and8 SPS long-term references. Source URLs/hashes attached;
third-party streams and rendered frames are not redistributed here.

GStreamer v4l2slh265dec produced I420 byte-identical to FFmpeg software
reference for ALL44 and500 frames (exit0, comparison0). Kernel path handles
these samples with a userspace implementation supplying the required controls.

Stock Chromium153 on Weston/V4L2 reports playback ended44/500 frames and
0/2 presentation drops. This is NOT a pixel-correctness pass. Final canvas
images differ from expected final software frames, and nearest matches are
earlier frames32 and448. Ordering/reference handling or test muxing remains
under investigation. Source patch chromium-rps is still NOT built/installed.

Raw HEVC remuxed into MP4 without edit lists; signed CTTS offsets constructed
from FFprobe decoded frame/packet positions. FFmpeg decoding of timed MP4
was byte-identical to raw software reference. Nonetheless a browser/container
timestamp interaction must be excluded before attributing the mismatch to
missing SPS/RPS controls. No claim of a solved browser SPS/RPS path.

Kernel log during the LTR browser run repeatedly reports `Long and short term RPS not set`. This independently confirms the known Chromium control-submission gap for this sample; it is separate from ordinary1080p60 presentation pacing.
