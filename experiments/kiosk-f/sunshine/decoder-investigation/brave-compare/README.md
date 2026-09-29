# Brave ARM64 isolated capability test

Official signed Brave APT repository, following https://brave.com/linux/.
Brave Browser153.1.95.104 / package1.95.104. Same Weston16 base and test3
kernel as Chromium. Sandbox enabled, network-none test container, GPU and
V4L2 nodes exposed, synthetic 1080p60 /1800frames.

Copy the existing Chrome comparison harness to tools/ and replace only
`exec google-chrome-stable` with `exec brave-browser`. run.sh records the
package version and executes the same fixtures. Build recipe uses a mutable
APT repository; pin versions before future reproducibility comparisons.

H264 ended with0/1800 HTML drops, but FFmpegVideoDecoder/platform=false.
HEVC returned NotSupportedError. No hardware video decoding profiles were
reported. Smooth software playback is NOT evidence of a hardware solution.
No no-pyramid performance comparison needed without a matching hardwarepath.
Production and release workflows unchanged. No browser installed onhost.

Test image ID: f5d86866ca618ce5fdcbce2cad01340356f565e82b2bbf96922522a4ec269c9d.
