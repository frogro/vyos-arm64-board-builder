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
