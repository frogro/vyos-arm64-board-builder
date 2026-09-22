# Board release channels

Registered channels live in `profiles/update-channels/`. Only the exact `network`
profile receives a channel; base and profiles including Tailscale or KVM do not.
Registered: `radxa-e52c` → `VyARM-Community/radxa-e52c` and
`rock-5b` → `VyARM-Community/rock-5b`.

The image contains `/usr/share/vyos-arm64-board-builder/update-channel.json`.
On a fresh installation the existing first-boot DHCP helper seeds the native
`system update-check url` only when no URL is already configured. No `auto-check`
or automatic installation is enabled. Existing saved configurations are not
rewritten during an image update. Administrators migrating those configurations
can set the channel URL explicitly:

```
configure
set system update-check url 'https://github.com/VyARM-Community/radxa-e52c/releases/latest/download/image-version.json'
commit
save
exit
add system image latest
```

The published `image-version.json` uses VyOS's native list format and refers to
an immutable release-tag ISO URL, not a moving ISO alias. The feed includes a
SHA-256 digest for traceability; stock VyOS is not claimed to verify this added
field. Download checksums can be verified separately. Existing board/profile
installer checks remain in force.

After publishing the central release, CI checks board/profile/architecture and
local checksums, uploads identical image and ISO files plus checksums and feed to
a draft board release, then publishes it as Latest. Failed uploads leave the
previous Latest intact. A failed publication can leave a draft requiring cleanup
before retrying. `RELEASE_TOKEN` must have release-write access to both repos.
The manual `Check board publication access` workflow verifies repository push
permission without printing or transferring the credential.

Public board descriptions describe VyOS and additional networking support;
profile identifiers remain in filenames and machine-readable compatibility data.

## Raspberry Pi 5

`VyARM-Community/raspberry-pi-5` publishes network installation images, using the
previously released `raspberrypi-native` / `firmware-files` boot chain. It does
not receive an update feed or ISO publication until native FAT kernel/initramfs/
DTB synchronization is hardware-tested. Experimental synchronization is now implemented; controlled ISO tests use the central build artifacts. This is distinct from
whether an installation image can be built successfully.

## Official Rolling watcher

`watch-upstream-rolling.yml` is scheduled twice hourly at minutes 23 and 53
on the default branch. GitHub may delay or drop scheduled events; this is
best-effort polling, not a guaranteed 30-minute detection interval. The second
slot adds another opportunity to check. Each run scans unprocessed releases,
and the persisted dispatch state prevents repeated board builds. A strict
interval would require an independent scheduler using workflow_dispatch with
dry_run=false. The manual dry-run remains available for read-only checks.
It checks official, non-draft, non-prerelease dated Rolling releases, starting
after baseline `2026.09.17-0028-rolling` (the reference already built manually).
For every new release it dispatches the network image for E52C, ROCK 5B and Pi 5
on `main`, with a fresh base and pinned Armbian metadata. It records each
successful dispatch in `.github/rolling-build-state.json` on `main` and does
not dispatch that board/release again. A shared concurrency group serializes
watcher runs. Existing matching run titles help recover interrupted dispatches.
An accepted build that subsequently fails is not retried indefinitely: inspect
its failure before rerunning. This workflow does not promise exact upstream
package equivalence. Source selection uses the build commit at the release tag's
timestamp; rolling package timing differences remain documented.

A manual dry run checks selection without dispatching or modifying state.
The watcher uses the repository-scoped GitHub token with contents/actions write;
board publication continues to use the existing release credential. No personal
credential is copied into the watcher.
