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
