# Native Wayland Sunshine integration — 2026-09-27

Bounded live check on ROCK, existing Panthor test kernel. New overlay based on github-36339240710, Sunshine binary dc7acada7dc2c9d744767b97e840d46eb7843358dd85617c915e8868148b0b01.

Native validation and environment/device generation executed on host. Same kiosk container runs Sunshine as kiosk, not root. Dedicated remote policy enables direct GPU/RGA, MPP device mappings, uinput and CSC companion. Weston receives all three owned virtual inputs automatically. CSC restores previous state when disabled. Portrait capture 270 / absolute input 90 derived from kiosk rotation 90.

35-second HEVC: 60.26 incoming / 60.22 rendering FPS, host average 12.9 ms, network drop 0%, jitter drop 0.07%. 30-second H264: 60.47 incoming FPS, host average 12.5 ms, network drop 0%, jitter drop 0.57%. Both have received audio packets; Opus initialized and PulseAudio monitor selected. Direct RGA frame counters increase at 60 FPS. No new subjective physical/mouse confirmation requested; earlier user acceptance remains separate.

Network limit: bridge-network forwarding attempt timed out. Streaming acceptance used temporary host networking with unchanged normal kiosk restored afterwards. This does NOT establish generic bridge/firewall reachability, nor a complete native CLI commit/save/reboot test. No automatic firewall widening or global host-network default added. Credentials were isolated copies of prior test state, never put in image/repository. Independent rollback timer armed before changing runtime.

Integration includes image staging + dynamic systemd generator (not merely the manual startup installer), runtime label gated CLI access, device grants, audio helpers, latest rotation binary, and verification of copied host helpers. Existing X11 and A-D configuration stays unchanged. 102 F tests pass; main preservation audit checks 8 A-D combinations and 31 packages. GitHub build is a test candidate, not release approval. Long duration, fresh SD and post-image update tests remain outstanding.
