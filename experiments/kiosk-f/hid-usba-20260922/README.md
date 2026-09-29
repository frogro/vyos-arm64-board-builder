# USB-A data path follow-up, 2026-09-22

User changed the PD injector data cable to USB-C–USB-A at the ThinkPad.
ROCK test4, USB-C controller fc000000.usb; keyboard-only isolated gadget.
The injector itself has no USB identity. ThinkPad sees VyARM Isolated HID test.

## Results

- Initial enumeration: configured, high-speed, HID keyboard input node present.
- no_out_endpoint=1: 200 presses + 200 releases, exact evdev sequence.
- Default no_out_endpoint=0: same 400 exact events.
- Three additional software unbind/recreate/bind cycles, default endpoint:
  all three pass 200 pairs each. These are not physical cable replug tests.
- No keys sent to desktop: EVIOCGRAB before sending; detach gadget before
  releasing grab even on failure. Independent 90s cleanup timer as fallback.
- First five input runs: 1000 presses and 1000 releases received, no repeats.
- Additional ~80s run: 2000 presses and 2000 releases, exact sequence.
  Sender exit0. Capture cleanup initially returned ENODEV on releasing the
  already-detached input device; corrected to tolerate only that expected
  error. No transfer failure inferred from this cleanup exception.

This supersedes a universal claim that high-speed fails or no_out_endpoint=1
is required. Earlier results were on another host connection AND the normal
kernel; this comparison does not isolate cable, hub, host controller or kernel.
No gadget driver patch required for this tested connection. Do not infer the
injector is defective. Composite keyboard/mouse/storage not retested here.

Host logs show usb1-port4 enable/enumeration errors before successful
usb1-1.3 enumeration through the Terminus USB2 hub. The warning alone does not
identify which cable/device is faulty. State snapshots taken two seconds after
bind precede completed enumeration; successful captured events are later.
Expected disconnect at each run end is our explicit cleanup.

Original vyos-kvm gadget was initially unbound and remained unbound: test4 DT
sets fc400000 to host, so the configured dedicated UDC is absent. fc000000 is
otg and available. Production touch is a separate USB-host input device.
Test gadget removed, restoration timer stopped. No permanent USB config edits.

Scripts are experiment records, requiring the session SSH helper
/tmp/av1-remote.py and remote /run/vyarm-usba-probe-cleanup.sh. Cleanup must run
through /bin/sh because /run is noexec; the first recognition probe exposed
that execution-policy issue and was cleaned up explicitly. Do not use scripts
as production installation tooling.
