# Fresh SD image live test, 2026-09-22

Kernel 6.18.50-vyos; runtime localhost/vyarm-kiosk:full-f-20260922.
Offline import completed (about 100 seconds); no failed systemd units.
Fresh image has no configured kiosk container. Tests use disposable containers,
packaged Chromium and media-policy helper, sandbox retained, headless GL Weston.
No physical HDMI assessment or default X11 hardware decoding claim.

All four short 1080p60 fixtures ended with V4L2VideoDecoder/platform=true:
H264 high reference: 600 frames, 4 dropped; HEVC Main10: 300/1;
VP9: 300/4; AV1: 300/2. No new kernel log entries during final check.
This does not establish sustained playback, error/reset recovery, or all bit depths.
The initial probe lacked the host render GID and used software decode. Runner
now obtains the numeric GID from the actual render node, not the container group.
Raw JSON including screenshots remains in /tmp/vyarm-fresh-decode-20260922 on
ThinkPad and ROCK; concise durable results are in results.json.

## CLI startup failure

Fresh /home/vyos lacked .profile and .bashrc despite both existing in /etc/skel.
Restoring only missing skeleton files immediately restored interactive configure.
The setup-links helper could create the home after passwd publication but before
useradd --create-home copied skel. It now waits for initialized shell files and
never creates the home. Regression test exercises that ordering. Existing custom
files are untouched. Fix installed live with original helper backed up under
/config/vyos-arm64-setup-links.before-shell-fix.sh. No reboot required.

The previously produced SD/ISO files are NOT repacked with this correction.
Their first-boot race remains until rebuilt; do not call those artifacts fixed.

## Required follow-up: complete Profile F first-install setup

User explicitly requests recording this missing build integration. Importing the
runtime and installing CLI alone does not provision a runnable kiosk. Add a
reviewable, explicit Profile F setup path which selects the versioned runtime,
sets persistent state, display/VT/udev access, discovers stable input identities,
and sets restart policy. Do not overwrite existing container configuration during
updates or activate experimental Wayland/decoder recipes merely by importing an
image. Provide a distinct supported Wayland setup if hardware browser decoding
is offered. Acceptance requires a fresh-image boot, working configure, kiosk
startup, display rotation/touch and restart, plus configuration-preserving update.
Until implemented, document required manual provisioning; do not advertise the
current SD/ISO as a ready-configured kiosk. User configuration currently pending:
local input-test page, auto output, 90 degrees, auto decode and both reserves on.

## Follow-up 2026-09-23

ROCK access restored. Existing kiosk running at 1080x1920/90 degrees on HDMI-1;
ILITEK touch and mouse devices present in Xorg; no failed systemd units.
Actual touch interaction not asserted. Sunshine disabled by current policy.
Native `request kiosk sunshine kiosk pair` and config-mode `run request ...`
both reached the Web username prompt; aborted before entering data. No credentials
or pairings changed. Current user-selected software decoder policy preserved.
78 local profile tests pass. New guarded setup helper refuses an existing kiosk
on the real system; first-install apply still needs fresh-image acceptance.

Corrected packaging started on NUC as user unit vyarm-corrected-image-20260923.
Source 9e76084, retaining kernel/Chromium/CLI/runtime inputs. Original outputs
retained. New directory /home/photobooth/vyarm-board-build-20260922/revised-20260923.
Includes first-login helper fix and explicit standard X11 setup helper. This is
NOT automatic Wayland provisioning and NOT a new Chromium/kernel compilation.
Build result must be read from status/log; start does not imply completion.
