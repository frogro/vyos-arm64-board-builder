# Automatic Rolling base lifecycle

The board-candidate GitHub workflow resolves `vyos_ref` (default `rolling`) to
one immutable official VyOS build commit before starting any image work.
With `raw_run_id` empty, it searches the latest 100 successful repository runs
for a non-expired ARM64 raw artifact with matching source provenance and raw
build recipe. A cache miss calls the raw workflow within the same workflow run;
the board job starts only after the raw job succeeds. No personal access token,
external scheduler, or workflow-dispatch permission is required.

Both the raw job and board kernel receive that resolved commit. A moving Rolling
branch during a build cannot change the board kernel's selected source. A later
board build resolves Rolling again and rebuilds the base when necessary. This
is on-demand refresh, not a scheduled build on every upstream commit.

The recipe fingerprint covers the raw workflow, VyOS source helper, ARM64 raw
patch and raw flavor. Provenance also records the container digest and VyOS
defaults. Mutable container tags and package repositories are not a complete
reproducibility guarantee; the final kernel ABI check remains mandatory. This
cache deliberately invalidates on source commits, not only kernel version.

An explicit raw run must be successful, unexpired and attest the same source
commit. For compatibility with manually produced test bases it may lack the
recipe fingerprint. Raw artifacts with no source provenance are rejected.
To reproduce an older test, explicitly specify both its source SHA and run ID.

API failures stop selection instead of silently falling back to an old base.
Failed base builds prevent board assembly and release publication. Concurrent
first builds for the same uncached snapshot can each build a base; they do not
reuse an unfinished artifact. Subsequent successful builds can reuse either
matching artifact. Artifacts produced by a failed overall candidate run are
not reused automatically.

The legacy `tools/resolve-raw-run.sh` remains available for existing manual
scripts; its latest-successful semantics do not provide this guarantee. The
board-candidate workflow now uses `tools/resolve-rolling-base.py` instead.

Validation: `python3 tests/test-rolling-base.py`,
`bash tests/test-vyos-source-ref.sh`, and actionlint on both workflow files.
