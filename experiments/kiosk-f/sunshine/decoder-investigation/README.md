# Decoder integration audit, 2026-09-21

The running test2 kernel and the HEVC Sunshine image do **not** establish video
hardware decoding. The following gaps were verified in the actual test2 source:

* `ROCKCHIP_MPP_RKVDEC2` exists in Kconfig and the Makefile names
  `mpp_rkvdec2.o` and `mpp_rkvdec2_link.o`, but their C sources and decoder headers
  are absent. The existing encoder patch includes compatibility shims and these
  declarations, not a complete decoder port. Enabling this option cannot build.
* The final test2 DTB lacks decoder cores and decoder IOMMU nodes. Power-domain
  and QoS nodes do not instantiate the decoder.
* The alternative upstream `rkvdec.c` in this source only matches
  `rockchip,rk3399-vdec`; enabling VIDEO_ROCKCHIP_VDEC does not add RK3588 support.
* Our FFmpeg static library build deliberately disables everything except the
  selected encoders and their dependencies. It disables programs and enables no
  decoder. Chromium uses its own media stack, not Sunshine's FFmpeg libraries.

## Pinned vendor comparison

See vendor-reference.json for the official rockchip-linux/kernel commit and
SHA256 of the examined files. Files were fetched for comparison only; they were
not copied into the kernel tree or applied live.

The vendor decoder also includes mpp_rkvdec2_link.h, SoC hack files, and BSP
OPP/system-monitor/IOMMU interfaces. Copying the two C files alone is insufficient.
Its RK3588 reset operations select rkvdec2_sip_reset. That function chooses SIP
or CRU reset based on CONFIG_ROCKCHIP_SIP. Existing local SIP/QoS compatibility
stubs must be audited against the actual selected reset/link paths; returning
success from a stub does not prove reset recovery works.

Vendor DT describes CCU, two decoder cores, five clocks per core, resets, decoder
IOMMUs, task queue 9, RCB/SRAM mappings and power domains. Its BSP-specific IOMMU
properties cannot simply be assumed to work with our upstream IOMMU driver.

## Required sequence before another decoder test kernel

1. Choose a complete, pinned decoder implementation and port its dependencies in
   a separate experimental patch. Keep the working encoder path intact.
2. Adapt matching SoC DT bindings, clocks, resets, IOMMU and RCB allocation.
   SoC-specific kernel descriptions are expected; runtime capability selection
   must not infer support from a board name.
3. Compile in a separate build directory; audit final config, DTB and module
   dependencies. Preserve test2 artifacts and boot rollback.
4. Exercise H264/HEVC decoding, reference frame output, repeated startup and error
   recovery with a matching standalone userspace decoder before browser changes.
5. Verify the specific Chromium/Qt media integration separately. A successful
   MPP/FFmpeg decode or Mali WebGL result alone does not establish browser decode.

No decoder activation, new test kernel, or new browser-decode claim accompanies
this audit. CPU video decoding remains the fallback.

## Isolated test3 backport, 2026-09-21

0001-experimental-upstream-rkvdec-backport.patch is an experimental delta on
the prepared 6.18.50 test2 source, not enabled by release builds. It overlays
the pinned v7.0 rkvdec driver, adds upstream HEVC extended SPS controls, applies
four subsequent HEVC bounds/RPS fixes, and adds RK3588 decoder/IOMMU/SRAM nodes.
Exact input blob hashes, fix commits and before/after file hashes are in
upstream-reference.json. The metadata-copy call retains the 6.18 third argument
(false). Existing encoder, GPU and audio changes remain in the base tree.

The complete patch passes a dry-run against the original source. Targeted
compilation of rkvdec, V4L2 core and rk3588-rock-5b.dtb succeeds with GCC15.2.
This is compile validation only: full link, live probe, reset/IOMMU recovery,
actual H264/HEVC decode and browser integration remain unverified.

Full build runs separately under user service vyarm-decoder-test3-build, -j1,
MemoryHigh=2G, MemoryMax=3G, Nice=10. Workspace:
/mnt/entwicklung/projekte/VyOS/arm/vyos-arm64-board-builder/tmp/kiosk-decoder-20260921
Config uses CONFIG_VIDEO_ROCKCHIP_VDEC=m and LOCALVERSION=-vyos-f-test3.
No test3 installation or reboot has occurred. No private signing keys belong
in this patch or repository.

## Isolated GStreamer decoder userspace

Containerfile.gstreamer builds official GStreamer/core/base/bad 1.28.7 tarballs
with SHA256SUMS, under /opt/gst inside a separate image. Fetch tarballs from
https://gstreamer.freedesktop.org/src/{package}/{package}-1.28.7.tar.xz into the
build context. No host/kiosk GStreamer packages are replaced. Native build uses
-j2 and a separate memory-limited service. v4l2codecs and H264/H265 parsers are
explicitly enabled. No decoder success is inferred from plugin compilation.

The bundled HEVC EXT_SPS ST/LT RPS structures were compared with test3 UAPI and
match field-for-field. The release contains the matching request-API support.
Reference: https://gstreamer.freedesktop.org/releases/1.28/ .

make-decode-fixtures.sh creates synthetic 720p H264/HEVC streams with B-frames
and software-decoded I420 references. test-stateless-decode.sh explicitly uses
v4l2slh264dec/v4l2slh265dec, checks exact output and three separate starts each.
Run only after identifying the new decoder's matching video/media nodes; no
hardcoded node numbering. It does not select MPP encoders or fall back to CPU.
Any mismatch needs investigation, not silent relaxation of the reference test.
These tests are prepared, not yet passed on hardware. Chromium integration and
malformed-input/reset recovery remain additional work after successful decode.

### Decoder remove-path caveat (source audit, not live failure)

Test3 still contains the original remove order: V4L2 cleanup, PM disable,
autosuspend disable, IOMMU-domain free. Community claims that an ordering patch
fixed VP9 were withdrawn by the patch author. v4 instead describes a clock
reference leak on unbind; a subsequent self-review reports an IOMMU use-after-
free window in that reorder and proposes splitting unregister/release. Do not
blindly import v2/v4 or claim it is an accepted VP9 fix. No such patch applied.
Repeated process starts are safe test scope; deliberate driver unbind/reload
requires additional audit before live testing. Test3 has its upstream hardware
soft-reset/IOMMU restore path, which is distinct from BSP reset_control patches.
Primary discussion and correction:
https://patchew.org/linux/20260717154505.83935-1-pavone.lawyer@gmail.com/

Browser probe preparation: browser-decode-probe.html plays one synthetic MP4
selected by ?codec=h264 or hevc, records frame callbacks, dimensions, completion
and dropped frames, and exposes window.decodeProbe. A page result alone never
proves hardware decode. Capture Chromium Media domain player properties/events
in the same session, including actual decoder name/platform flag; cross-check
kernel decoder activity. Use a temporary profile and isolated container, retain
sandboxing, and do not expose the debugging endpoint on the network. Fixture MP4
files are generated locally, not committed. Do not change the production kiosk.

## TODO: Chromium HEVC extended SPS/RPS controls

Explicitly requested by user on2026-09-21. Track separately from kernel and
GStreamer decoder validation:
- Audit installed Debian Chromium patches and candidate Google Chrome against
  upstream153 H265 delegate for V4L2_CID_STATELESS_HEVC_EXT_SPS_ST_RPS and
  V4L2_CID_STATELESS_HEVC_EXT_SPS_LT_RPS (absent in examined upstream delegate).
- Check driver requirements and parser data availability; use GStreamer1.28
  implementation/UAPI as a reference, not a blind source transplant.
- If missing in the active path, implement capability-checked control submission
  with validated array bounds/counts and compatible behavior on older drivers.
  No board-name switch and no mandatory new control on unsupported hardware.
- Test SPS short/long-term reference sets, B-frames, repeated starts and decoded
  output against software references, then actual Chromium decoder diagnostics.
- Keep changes isolated and preserve production browser until verified.
Status: TODO; no browser patch implemented or hardware success claimed.
