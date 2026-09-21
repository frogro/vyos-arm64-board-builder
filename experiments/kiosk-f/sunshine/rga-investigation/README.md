# Isolated RGA investigation — 2026-09-20

Not connected to any build workflow. No driver was replaced or unloaded.
Kiosk, Sunshine, network configuration and modem were not modified.

## Live evidence

The original synthetic test again fails on 6.18.50-vyos: maximum sampled error
20 for BT.601 and 16 for BT.709 against limited-range references.
The new four-case sweep requests full and limited NV12 output with full RGB
input. Within each color matrix the entire output is byte-identical (see JSON
SHA256 values). Thus requested output range does not affect this conversion.
The sweep deliberately keeps its comparison reference limited for both requests;
its pass/fail is not a full-range accuracy test. This is diagnostic, not a
stream performance benchmark. Tests open only the identified RGA mem2mem node.

Stable Linux v6.18.50 sources store colorspace separately; hardware CSC selection
uses that field, not requested quantization. G_FMT rebuilds format fields and
does not restore quantization/ycbcr encoding. A final fix must correctly
negotiate and report supported matrix/range combinations as well as program
the hardware; unsupported combinations must be rejected or handled in software.

## Diagnostic patch, NOT a production correction

0001-diagnostic-bt601-destination-mode.patch changes only the RGB-to-YUV
destination BT.601 mode from 1 to 2. This follows the vendor FAQ mapping of
full-range mode 1 versus limited-range mode 2. It is a bounded hypothesis to
test with the existing limited-range probe. It leaves YUV-to-RGB unchanged.
Dry-run application to stable v6.18.50 passed; compilation and live execution
have NOT been performed. It does not implement range negotiation, handle all
colorspaces, or fix BT.709. Do not add to production kernel patches unchanged.

## Why live module replacement is currently blocked

- Running kernel has CONFIG_MODVERSIONS=y and CONFIG_MODULE_SIG_FORCE=y.
- Installed rockchip-rga module is signed with the build-time VyOS kernel key.
- No matching prepared kernel tree/Module.symvers was found locally or on ROCK.
- Matching release 2026.09.19-1517-selfbuilt-rock-5b-network-tailscale-kvm lists
  kernel.config and kernel.release, but no prepared headers, Module.symvers or
  module-development bundle. No trusted signing key is available in this work.

A same-version build alone is insufficient: replacement needs matching ABI and
a signature trusted by this kernel. Do not disable signature enforcement or
force-load a module. If the exact build workspace/key cannot be recovered,
prepare a separately bootable F test kernel and signed modules together, keeping
the working boot image as rollback. Retain build metadata and symbol versions
for further tests; never publish private signing keys in release artifacts.

## Next controlled test

Run baseline and candidate with the same synthetic colors, including intermediate
gray levels and both matrices/ranges; confirm negotiated metadata. Preserve
stock module and kernel. Only integrate RGA into Sunshine after accuracy tests
pass and actual streaming demonstrates an advantage. Until then swscale remains
the working conversion path.

Sources:
- https://github.com/gregkh/linux/tree/v6.18.50/drivers/media/platform/rockchip/rga
- https://github.com/airockchip/librga/blob/main/docs/Rockchip_FAQ_RGA_EN.md (Q2.14)
- https://docs.kernel.org/admin-guide/module-signing.html

## Test2 kernel result (2026-09-21)

Booted 6.18.50-vyos-f-test2 with matching DTB and signed modules. Re-ran the same
probe without altering the kiosk. RGA identified as /dev/video1 (discovered by
driver name, not hardcoded). BT.601 limited reference: maximum sampled error1,
improved from20. BT.709 still maximum16. Full/limited requested outputs remain
byte-identical within each matrix and returned quantization is Default.
Raw report: range-sweep-test2-20260921.json. Overall test exits1 intentionally:
this is not full range negotiation/correctness. Do not switch Sunshine from
swscale on this evidence. Driver diagnostic change benefits BT.601 only.

## Extended gray/range diagnostic (2026-09-21)

`range-sweep-probe.py --extended` adds eight neutral gray patches and compares
full-range requests against an actual full-range reference. Legacy invocation
retains the previous diagnostic reference for reproducibility. All patches have
even boundaries; samples are taken at stripe centers.

Test2 measured BT.601 limited max error 1; BT.601 full max error 20;
BT.709 limited max error 16; BT.709 full max error 20. Requested full/limited
output remains identical. BT.709 gray inputs 16,32,64,96,128,160,192,224 produced
Y 16,32,64,96,128,159,191,223, whereas limited reference is
30,43,71,98,126,153,181,208. Black/white still produce 16/235.
This suggests approximately full-range luma followed by limited clipping, not
correct limited-range scaling. It is a hypothesis, not a proven register fix.
Vendor FAQ Q2.14 maps RGB2YUV BT.709 limited to mode 3, matching current selection;
blindly replacing that mode is unjustified. Need compare actual RGA2 register
programming/core revision and vendor implementation before a driver change.
The SRC/DST BT709 macro typo is numerically harmless (both 3).
