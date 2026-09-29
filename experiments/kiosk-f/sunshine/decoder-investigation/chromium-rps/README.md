# Chromium 153 HEVC SPS/RPS experiment

Status 2026-09-21: **source patch and isolated tests only; no complete patched Chromium
build or patched-browser result, no production integration**.

Target: upstream Chromium tag `153.0.8010.47`, matching the kiosk browser version.
The patch preserves short-term RPS coded syntax in the parser and sends the
optional upstream V4L2 extended SPS short/long-term controls. The conversion uses
capability queries, not board names. EINVAL means an old driver without the
optional control; other ioctl errors and incompatible payload sizes fail closed.
Zero-count controls are omitted. Payloads remain alive through S_EXT_CTRLS.
Long-term entries use the values already retained by Chromium.

## Provenance

- Chromium sources: https://chromium.googlesource.com/chromium/src/+/153.0.8010.47/
- UAPI structures/IDs match the experimental test3 kernel and GStreamer 1.28.7
  `sys/v4l2codecs/linux/v4l2-controls.h`.
- GStreamer 1.28.7 `gstv4l2codech265dec.c` was used to check dynamic control
  submission and empty-array handling; conversion implementation here is new.
- Existing Chromium calculated reference-picture lists remain in use; the
  additional fields retain raw syntax previously discarded by ParseStRefPicSet.

Apply inside a clean matching Chromium source tree:

```sh
git apply --check /absolute/path/to/0001-chromium153-hevc-sps-rps.patch
git apply /absolute/path/to/0001-chromium153-hevc-sps-rps.patch
python3 /absolute/path/to/test-parser-conversion.py /absolute/path/to/chromium/src
```

The test extracts the patched real `H265StRefPicSet`, `ParseStRefPicSet`, mapping
helper, and control-submission lambda. A small bit reader replaces Chromium's
parser infrastructure; the capability ioctl is mocked. g++ C++20 with ASan and
UBSan checks explicit/predicted RPS, inferred use flags, destination reuse,
truncated input, DPB/payload bounds, ABI sizes, missing controls, ioctl failure,
payload mismatch and dynamic-array capacity. It is deliberately **not** reported
as a complete Chromium unit test or a driver test.

## Remaining gates before deployment

1. Full Chromium parser and V4L2 delegate compilation, including Chromium's
   unsafe-buffer diagnostics, GN/sysroot compatibility and original parser tests.
   Default equality now includes preserved syntax; check any expected test values.
2. Add full-project parser/accelerator tests, including long-term references,
   multiple SPS changes and request submission against the actual driver.
3. DONE: test3 safely booted; V4L2 nodes confirmed. Independent GStreamer
   H264/HEVC and SPS/LTR reference comparisons pass. Stock Chromium hardware
   decode works for ordinary fixtures; RPS sample correctness does not pass.
   See ../rps-conformance-test3 for kernel missing-control evidence.
4. Build an isolated browser with Linux V4L2 enabled. Merely applying this patch
   does not ensure the distribution browser enables/selects that backend.
5. Keep Chromium sandbox enabled; demonstrate actual hardware decoder selection,
   decoded frame correctness, repeated starts, and absence of kernel faults.
6. Only after these gates consider an optional builder path. No release workflow,
   standard F/D image, existing kiosk, or default configuration is changed here.
