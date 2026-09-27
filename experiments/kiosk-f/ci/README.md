# Isolated NUC / GitHub Actions A-D+F comparison

One-off candidate for ROCK 5B; no automatic release publication or main changes.

Frozen integration source: `8c5a006`; upstream VyOS `999.202609250800` from
successful A-D run `36267716867`; original CLI source
`4e3e38a2e665bb2d8e9446116e02300bb38a2ab4`.

The native ARM64 Actions job rebuilds the full CLI with its upstream checks.
Its recipe must equal `f7a18d9dddcaef2028f969fb271062918e4a8e20b13e071d38f297db95c738fd`.
It reuses the exact same validated kernel/modules/DTB, Chromium/Kiosk runtime,
GPU firmware and build-container layers as the NUC run. Binary inputs are staged
as draft-release assets, pinned by SHA256 in inputs.sha256; they are not a public
release and the job only has read access to repository contents. Outputs are
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
