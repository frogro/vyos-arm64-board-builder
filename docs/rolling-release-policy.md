# Published Rolling policy and recovery path

The board candidate and ARM64 raw workflows default to `published-exact`.
This is a safety gate, not yet a completed release reproduction implementation.
Currently it identifies the newest official Rolling release and stops before
compilation: no release-attested ARM64 package source is integrated. It never
falls back to rolling HEAD or treats an AMD64 release tag as a vyos-build ref.

The 2026.09.17-0028-rolling release publishes an AMD64 ISO and SBOMs. Its tag
belongs to vyos-nightly-build; a corresponding tag was not found in vyos-build.
The SBOM records package versions but does not by itself provide the matching
ARM64 binaries. Our raw builder uses a mutable rolling package repository and
container, so pinning just the build commit does not establish parity.

To restore the previous behavior explicitly, choose `source_mode=development-source`
in workflow_dispatch. `vyos_ref=rolling` then selects current development HEAD;
an explicit source ref is also possible. This mode does NOT promise published
release equivalence. The UI describes this limitation. No automatic fallback.

The previous complete code is preserved remotely on
`backup/rolling-head-before-release-policy-20260919` (03d71e6).
An emergency workflow dispatch on that ref restores the original pipeline.
No image was built as part of this policy change.

Before enabling exact builds, implement and verify:

1. Official release-to-source provenance, without date-based guessing.
2. Available ARM64 packages matching release package versions, with immutable
   package indexes/artifact checksums and pinned build inputs.
3. A final package/version comparison; explicit documented differences for the
   custom board kernel, firmware and optional profiles (whole-image byte identity
   across AMD64 and ARM64 is not a meaningful requirement).
4. Cache reuse keyed by release provenance and package lock, and published
   provenance evidence alongside every image.

Until then, exact mode intentionally refuses to publish an unverified image.
