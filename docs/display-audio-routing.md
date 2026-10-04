# Shared display audio for profiles F and G

Both container profiles use `experiments/kiosk-f/container/kiosk-audio.py`.
The G entry point imports that same implementation; both container build paths
already include the file. This policy is not conditional on a board name.

A private PulseAudio server starts with a null sink, without card auto-discovery.
The selected DRM connector's EDID is matched against ALSA ELD identity and audio
capabilities. Only an unambiguous matching card with one playback PCM is opened.
Unconnected ports, displays without audio, and ambiguous matches remain silent.
No arbitrary card-number fallback is used. The null sink retains a capture source
for remote audio even without a local audio-capable display. Physical speakers
cannot be detected: a monitor may advertise HDMI audio for a line-out socket.

F resolves its compositor's display.json output (including X11 HDMI name mapping)
against DRM connectors. G supplies its already selected DRM card/output directly.
The selection is checked periodically; sink inputs move when the output changes.
Failed ALSA opens are retried with a 30-second delay. Complex cards exposing
multiple playback PCMs are deliberately not guessed; they require further mapping.

Validated on Orange Pi 5 Plus using both existing container images with the new
module mounted temporarily: connected HDMI selects plughw:0,0, unused HDMI stays
unopened, and no new HDMI codec kernel errors appear. This is a device-opening
check, not a listening test or a hardware validation of other boards. Unit tests
cover selection, missing audio, ambiguous matches, X11 output names and hotplug.

The change requires rebuilding F/G container images; a kernel rebuild is not
needed for this fix. Profiles without F/G are unaffected.

## Host mixer state and kiosk lifecycle

The KVM/media host package set now includes `alsa-ucm-conf`. The ALSA restore
service uses a per-card helper: existing UCM profiles are retained; only
libasound ENOENT selects generic initialization for that card. Missing UCM
package data, malformed profiles and device errors remain failures. On a fresh
installation it initializes mixers then saves their actual state, instead of
restoring a nonexistent file. Debian init's documented-in-00main status 99
means generic defaults were applied and is accepted only during initialization.
No board-independent mixer state is shipped. Network-only images are unchanged.

The two generated kiosk input helpers use After, BindsTo and PartOf referencing
the native container service. Orange Pi live tests covered start, restart, stop,
start again and native CLI removal without a restart of a deleted unit.
The new ALSA helper was also tested on all four Orange Pi audio cards with a
fresh temporary state file and a subsequent restore. This does not constitute
a hardware audio test on other boards or a reboot test of a newly built image.
