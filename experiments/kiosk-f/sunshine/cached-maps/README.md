# Panthor cached-mapping experiment, 2026-09-27

Status: isolated source prepared; all Panthor objects compiled successfully for
arm64 against the local 6.18.50 test4 configuration. Not boot-tested, not a complete
bootable kernel artifact, and no measured Sunshine speedup. Main, release workflows,
and the running ROCK kernel are unchanged.

## Applied scope and provenance

The upstream `Cached maps and explicit flushing` series is archived in `upstream/`
with commit URLs and SHA-256 hashes. The **applied** file is
`panthor-6.18.50-backport.patch`, not the raw archived series.

For RK3588 it includes Panthor patches 1–7, prerequisite timestamp propagation
`d8f94cb02af3` (driver 1.6 must exist before advertising 1.7), plus later fixes
`c57079937bf8` (device exit on invalid BO flags) and `76e8173ba92e`
(cache-sync argument order). The coherency correction `9beb8dca9e74` already exists
in this baseline and is not applied twice. Two neighboring-function contexts were
adapted without adding unrelated GPU L2 or firmware-state features.

The Panfrost kernel half (8–13) and its `a34340574bad` follow-up are archived for
reference, **not applied**: that driver serves different Mali generations and has
additional version dependencies. This is not a claim of support for every SBC.

Baseline: `tmp/av1-iommu-test4/source` in the builder, kernel 6.18.50.
`baseline-files.json` records exact before/after hashes for all eight changed files.
The source may differ from the current production kernel; use the guard rather than
assuming version-string equality is sufficient. The existing decoder/RGA source
changes are retained by copying the whole baseline.

## Reproduce preparation

Run `python3 prepare.py BASELINE_SOURCE NEW_SOURCE_DIRECTORY`. It refuses a reused
destination or different baseline and does not modify the baseline. The destination
parent must exist. Run builds in a separate output directory:

```sh
mkdir -p "$TEST_ROOT/kbuild"
cp "$BASELINE_OUTPUT/.config" "$TEST_ROOT/kbuild/.config"
"$TEST_ROOT/source/scripts/config" --file "$TEST_ROOT/kbuild/.config" \
  --set-str LOCALVERSION '-vyarm-panthor-cache-test'
make -C "$TEST_ROOT/source" O="$TEST_ROOT/kbuild" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -C "$TEST_ROOT/source" O="$TEST_ROOT/kbuild" ARCH=arm64 \
  CROSS_COMPILE=aarch64-linux-gnu- -j2 drivers/gpu/drm/panthor/
```

A bootable candidate additionally requires the normal complete Image/modules/DTB,
signing and packaging process. Do not replace just a loaded graphics module or
reuse the production kernel release string for installation. Boot testing requires
a separate boot entry, preserved normal entry and independent rollback.

Local prepared source and successful object-build log:
`/mnt/entwicklung/tmp/panthor-cached-maps-20260927/{source,compile.log}`.

## Mesa and the OpenGL limit

Audited Mesa mirror revision `85fdb7070c3533021f5e1dc40b38ce1140aabc68`:
`src/panfrost/lib/kmod/` supports WB_MMAP, and Vulkan/PanVK requests it. No WB_MMAP
request occurs in the audited `src/gallium/drivers/panfrost/` OpenGL driver.
Thus the kernel interface is API-neutral, but installing this kernel alone does
not establish cached readback for Sunshine's OpenGL `GetTextureSubImage` path.
No unflushed cached mappings are forced into OpenGL in this experiment.

Sources:
- https://www.mail-archive.com/dri-devel@lists.freedesktop.org/msg579708.html
- https://gitlab.freedesktop.org/mesa/mesa/-/merge_requests/36385
- https://github.com/chaotic-cx/mesa-mirror/tree/85fdb7070c3533021f5e1dc40b38ce1140aabc68/src/panfrost

## Later comparison, without recompiling Sunshine for each kernel

Use the same instrumented Sunshine binary from `../kms-timing/` in every row;
`SUNSHINE_VYARM_KMS_TIMING=1` enables stage timings. Keep MPP, codec, bitrate,
resolution, rotation, scene and client identical, and record actual renderer.

1. Original kernel + existing Mesa: control (KMS readback stage timings).
2. Cached-map kernel + same Mesa: regression/control; no assumed cache benefit.
3. Cached-map kernel + separately pinned newer Mesa: OpenGL timings and correctness;
   prove a cached allocation is used before attributing any improvement to it.
4. Separate PanVK experiment, with/without `PANVK_DEBUG=no_wb_mmap`, where supported.
   A successful Vulkan allocation test does not validate Sunshine OpenGL capture
   or prove a hardware Vulkan video encoder exists on the ROCK.

Measure stage latency, delivered frames, CPU use and visual correctness. Exercise
restart and GPU error logs. Keep normal Kiosk configuration/state backed up and
restore it after each live run. No automatic deployment or boot is performed here.
