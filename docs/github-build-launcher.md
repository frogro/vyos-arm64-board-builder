# GitHub board-build launcher

`trigger-release.sh` is the interactive and non-interactive entry point for
dispatching `build-board-candidate.yml`. It does not build a kernel locally.

Before dispatching, the launcher:

- verifies GitHub CLI authentication and the workflow ref;
- resolves the selected Armbian metadata to an exact commit;
- asks for the optional Extended Network, Tailscale and KVM-over-IP profiles;
- defaults release publication to disabled;
- finds the newest successful `test-vyos-arm64-raw.yml` run whose
  `vyos-arm64-raw` artifact is still available;
- validates a manually pinned raw run in the same way;
- prints the complete request and requires final confirmation.

Use a dry-run for a safe end-to-end selection and validation test:

```text
./trigger-release.sh --dry-run --no-publish-release
```

No workflow is dispatched in dry-run mode. Armbian metadata and GitHub state
are still read so that the displayed request is actually usable.

For a reproducible build, pin the raw input explicitly:

```text
./trigger-release.sh --raw-run-id 32008814114 --no-publish-release
```

Direct workflow dispatches may leave `raw_run_id` blank. The workflow then
performs the same successful-run and unexpired-artifact resolution itself.
