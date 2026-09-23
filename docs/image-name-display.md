# Full image names in `show system image`

Numeric-looking names such as `999.202609230456` are identifiers, not numbers.
VyOS image_info.py passed them to tabulate with automatic numeric parsing, so
both that name and `999.202609210635` were displayed as `999.203`. The details
view could also round its Name and Version columns. This is independent of
board, architecture, and profile; it does not require changing stored names.

The builder applies tools/patch-vyos-image-info.py to the offline root after any
optional vyos-1x package installation. Both formatting functions pass
`disable_numparse=True`. Existing detail-column alignment is preserved; image
selection, raw output, installation, configuration copying and boot logic are
unchanged. SD images and update ISOs inherit the same corrected root filesystem.

The patcher handles line wrapping/trailing commas, is idempotent, accepts an
upstream `disable_numparse=True` fix and fails before writing on unrecognised
function/call structure. This makes a changed Rolling source visible during the
build rather than silently producing an unpatched image.

Regression tests reproduce the reported rounding using real tabulate, check
both views with release names, leading zeros, scientific-looking and ordinary
names, and check idempotency/source-change guards. Locally tested with tabulate
0.8.9 and 0.9.0; the board build runs the test with 0.9.0 in an isolated venv.
The existing system-image DTB, ARM CPU, feature-profile and vyos-1x-profile tests
also pass. A full board-image build has not been rerun just for this display fix.
Already-published images are unchanged; the next build from updated main embeds
the correction.
