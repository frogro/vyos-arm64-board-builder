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
