# Isolated NUC / GitHub Actions A-D+F comparison

One-off candidate for ROCK 5B; no automatic release publication or main changes.

Frozen integration source: `c0e39171807e14959611cfaa943e392f5d3b79db`; upstream VyOS `999.202609250800` from
successful A-D run `36267716867`; original CLI source
`4e3e38a2e665bb2d8e9446116e02300bb38a2ab4`.

The native ARM64 Actions job rebuilds the full CLI with its upstream checks.
Its recipe must equal `e4ba6e3c140350063eb20d95ee41fc70c34e8bb48b6e4f267003078ecaceee22`.
It reuses the exact same validated kernel/modules/DTB, Chromium/Kiosk runtime,
GPU firmware and build-container layers as the NUC run. Binary inputs are staged
as draft-release assets, pinned by SHA256 in inputs.sha256; they are not a public
release. GitHub requires contents:write to read these draft assets; the job has
no publication or repository-write step. Outputs are
Actions artifacts, not published board releases.

The SD image uses a12GiB disposable source copy; the original A-D artifact stays
unchanged. Standard builder assembly and ISO scripts are used. The same native
SquashFS version as on the NUC is supplied with its shared libraries, including
the lazily loaded libgcc_s dependency, and checked by a round-trip before use.

Compare embedded kernel/runtime hashes, CLI source/recipe and generated command
ownership, module trees, configuration defaults, host fixes, boot layout, and
payload identity between each run's IMG and ISO. Whole artifact hashes need not
match: build timestamps, filesystem UUIDs, compression threading and generated
package metadata can legitimately differ. Fresh boot/update testing remains a
separate step after artifact validation.

This corrected candidate follows the original 8c5a006 comparison. It normalizes
installed MPP library ownership and CLI metadata permissions, and removes the
upstream duplicate console log definition before CLI generation. Both package
and final image checks validate the resulting console commands.
