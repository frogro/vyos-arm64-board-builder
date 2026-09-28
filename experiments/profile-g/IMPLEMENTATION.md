# Profile G implementation and verification

## Scope

A separate Podman image, based on the tested Debian trixie F runtime, receives
AirPlay through UxPlay, GameStream through Moonlight (Sunshine is the sender),
and experimental Miracast through MiracleCast. One mode owns the HDMI display.
No receiver is enabled by default. E remains the remote-maintenance client.

G reuses F's counterclockwise rotation mapping and private PulseAudio lifecycle.
It does not claim that Chromium's decoder patches automatically accelerate
GStreamer or Moonlight: these use separate decoder implementations. `auto`
allows normal decoder selection, `software` requests software, and `hardware`
fails if a compatible decoder is unavailable. GStreamer plugin availability
alone is not proof of successful decoding or zero-copy presentation.

Native container CLI additions are generated from upstream source, including
normal reference-cache generation. No installed CLI cache is patched.
`--receiver yes` in the package builder / `RECEIVER_G=yes` in assembly opt in.
The feature selector accepts `--receiver-g yes`; generate the matching selection
file (and receiver-suffixed build profile) before assembly. Existing default
profile selections remain unchanged. G runtime artifacts are built separately
and loaded with `podman load`; automatic offline image bundling is not yet wired.

## Build

On a native ARM64 build machine with a local tested F runtime:

```sh
CONTAINER_ENGINE=podman bash experiments/profile-g/build-runtime.sh \
  localhost/vyarm-kiosk:TESTED-TAG /path/to/new/g-artifacts
```

Use the actual tested tag, not the placeholder. This produces runtime.tar,
runtime.json (hash, base image ID, source commit) and build.log. The source tree
must be clean for a reproducible build. The full container includes pinned
receiver sources. No source branch follows an unpinned HEAD at build time.

`Profile G receiver checks` runs policy/regression tests and compiles all three
receivers on native ARM64. This is not a full SD/ISO build or a hardware test.

The native CLI package must be rebuilt with `--receiver yes`. A prior F-only
package does not contain these commands. Load the G runtime locally before
committing: verification checks its profile-G image label.

## Native CLI example (after installing that package and runtime)

Each command is a separate VyOS configuration-mode command. Device names must
be checked on the target, especially the DRM card and decoder devices.

```
set container name receiver image localhost/vyarm-receiver:g-COMMIT
set container name receiver allow-host-networks
set container name receiver memory 2048
set container name receiver shared-memory 256
set container name receiver restart no
set container name receiver device display source /dev/dri/card0
set container name receiver device display destination /dev/dri/card0
set container name receiver device render source /dev/dri/renderD128
set container name receiver device render destination /dev/dri/renderD128
set container name receiver volume udev source /run/udev
set container name receiver volume udev destination /run/udev
set container name receiver volume udev mode ro
set container name receiver volume state source /config/receiver/state
set container name receiver volume state destination /state
set container name receiver volume state mode rw
set container name receiver receiver method airplay
set container name receiver receiver name VyOS-TV
set container name receiver receiver output auto
set container name receiver receiver rotation 0
set container name receiver receiver decoder auto
set container name receiver receiver resolution 1920x1080
set container name receiver receiver fps 60
```

Grant the actual audio, decoder and local input character devices using the
same explicit `device ... source/destination` syntax. Do not grant the full host
/dev or a privileged container. Hardware decoder nodes differ by kernel/device.
Stop/disable the F container before enabling G on the same DRM card; the new
verification rejects configured simultaneous ownership. It does not forcibly
stop an existing kiosk. Check for non-VyOS processes holding DRM too.

After `commit`, AirPlay advertises via mDNS. The first-connection PIN appears in
container logs. Keys and client registration remain under the /state volume.
This is screen mirroring, not a promise of DRM-protected video playback.
Host networking deliberately exposes the receiver to reachable host interfaces;
use the existing VyOS firewall policy for the intended LAN. No firewall rules,
UPnP, router APs or global network managers are changed automatically.

Moonlight first pairing (GUI on the attached TV, local mouse/keyboard required):

```
set container name receiver receiver method moonlight
set container name receiver receiver mode pair
commit
```

Add/pair the sender in the GUI; enter Moonlight's displayed PIN in Sunshine on
the sender. Then select streaming:

```
set container name receiver receiver mode receive
set container name receiver receiver host 192.168.178.84
set container name receiver receiver app Desktop
set container name receiver receiver codec h264
set container name receiver receiver bitrate 20000
commit
save
```

The host address is an example. `codec` accepts auto/h264/hevc/av1. No codec is
considered hardware-tested on G yet. System-key capture is disabled so the
client does not deliberately trap desktop shortcuts; physical behavior remains
to be tested. Mode changes restart only the G container; /state persists.

## Miracast and MediaTek

The curated driver list contains CONFIG_MT7921U/mt7921u and
CONFIG_MT7925U/mt7925u. Do not infer working Miracast from a chip label alone.
Read-only preflight:

```
show display-receiver wireless
show display-receiver wireless interface wlan1
```

P2P-client and P2P-GO must be advertised by the running driver. All interfaces
on the same PHY must be unused/down and free of addresses and bridge ownership;
the candidate VyOS wireless configuration must not own that radio. Initially
use a dedicated USB dongle. Same-radio AP/P2P concurrency is deliberately not
enabled merely because a driver advertises it.

```
set container name receiver receiver method miracast
set container name receiver receiver wifi-interface wlan1
set container name receiver receiver latency 50
set container name receiver capability net-admin
commit
```

The WLAN name is an example. Miracast uses a private container D-Bus and a
scoped miracle-wifid --interface; it never mounts the host D-Bus or stops host
NetworkManager/hostapd/wpa_supplicant. NET_ADMIN with host networking remains a
broad privilege: the code scopes its operations, not the Linux capability.
The device check runs again before start. A USB unplug ends the test, not an
automatic takeover of another interface. UIBC is not enabled in this first
implementation. The external GStreamer player uses bounded queues and a
configurable RTP jitter buffer; latency is a target, not a measured guarantee.

## Acceptance still required

- Full G container build atop the selected F artifact and native CLI package.
- Local TV output/audio, sender pairing and repeated disconnect/reconnect.
- Measure actual decoder selection, CPU load, frame pacing and end-to-end
  latency for equal 1080p60 LAN/WLAN conditions, not decoder-only FPS.
- Dedicated USB radio P2P negotiation, cleanup and AP regression check.
- Update/reboot persistence of both AirPlay and Moonlight identities.
- Controlled comparison with internal radio only after dedicated-radio success.

Steam Link and Google Cast are not selectable placeholders: their suitability
for this Linux ARM64 receiver remains research work. No full image or live
stream is considered verified by a passing command-generation test.

## Initial checks on 2026-09-28

19 G policy/source tests and 106 F tests passed locally, along with the existing
native profile and KVM CLI/config/supervisor tests. Applying F then G to the
actual pinned upstream container.py/container.xml.in succeeded without replacing
existing definitions. The main-preservation audit passed. The GitHub policy job
also passed; receiver compilation is recorded separately in its run.

A read-only live check found wlan0, driver mt7921e, running VyOS-AP. Its PHY
advertises P2P-client, P2P-GO and P2P-device. No second wireless interface was
present. This is capability evidence for the internal radio, not a successful
Miracast test and not proof of simultaneous AP/P2P operation. The AP and kiosk
were not stopped or reconfigured.

Native ARM64 build evidence:
https://github.com/frogro/vyos-arm64-board-builder/actions/runs/36390680164
completed successfully for cdb8b11: all three pinned receivers compiled and
help/startup smoke commands passed. Artifact: profile-g-backends-arm64.
The follow-up run for b6af4ea also checks session-bus/cleanup changes. Neither
run builds the final F-derived display container or proves an on-screen stream.
