# A–D promotion to main, 2026-09-22

Scope: merge the released main-test builder into main. Only existing base,
network, Tailscale and KVM features are included. No profile E/F development,
Chromium candidate or experimental decoder kernels are imported.

## Recovery points

- main before promotion: b710a82733bacdb82799a5b7449fc606b5d6cca5
- tested main-test: e24a9f11685eaa3e2ec11d81183f0c2556095f3c
- backup tags: backup/main-before-abcd-20260922 and
  backup/main-test-before-abcd-20260922 (preserve permanently).
- main-test is retained unchanged as a manual-build fallback.

Merge resolution: retain main-test's three-board publication credential check;
retain main's Rolling dispatch state to prevent duplicate releases. Watcher
checkout and dispatch now use main. Source-package CI also follows main.
The local package build helper resolves its own checkout instead of hardcoding
another worktree. Manual launcher already selects its current branch.

## Validation and rollout

Run all Python tests, shell checks and workflow lint. Watcher dry-run must not
write state or dispatch builds. Pause the watcher briefly during publication,
refresh main and preserve any newly recorded dispatches, push without force,
run a manual dry-run on main, then re-enable the watcher.
Existing successful builds at the retained main-test commit are reference
artifacts, not proof of a new complete image build. Perform an artifact-only
ROCK 5B network+Tailscale+KVM candidate from promoted main as the integration
regression; no release publication for that test.

## Fallback

Disable watch-upstream-rolling.yml if the promoted orchestration fails.
For manual recovery builds select main-test (verify it still points to the
recorded SHA), using publish_release=false initially. Existing published images
and live boards are unaffected by the Git merge.
To restore automatic builds, make a forward fix setting watcher checkout and
dispatch back to the retained main-test branch, preserve the CURRENT
.github/rolling-build-state.json, validate with a dry-run and re-enable.
Never force-reset main or restore an old dispatch-state file: either can lose
history or duplicate publication. Kernel/device fallback remains independent.

## Checked before publication

All 38 Python test programs passed. The 13 shell test programs initially
encountered two missing local-cache prerequisites; both passed after connecting the existing 6.18.44 source cache.
All 13 shell test programs therefore passed; test outputs stayed in the
isolated worktree.
Actionlint 1.7.12 passed with external shellcheck disabled; changed launcher
shell syntax and git diff whitespace checks passed. Live watcher DRY_RUN=true
completed without dispatch or state writes. Image assembler, feature derivation,
board workflow and profiles are unchanged from e24a9f1.
