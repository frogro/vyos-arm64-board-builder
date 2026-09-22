# USB-C HID diagnostic, 2026-09-22

ROCK normal kernel 6.18.50-vyos, fc000000.usb via user's PD injector, ThinkPad xHCI. Production gadget uses fc400000.usb.

Full-speed minimal keyboard with no_out_endpoint=1: 20 press/release pairs received under EVIOCGRAB. Restoring default no_out_endpoint=0 reproduced a write timeout; a delayed press escaped after the receiver released its grab and caused repeated a characters. The harness must detach the gadget BEFORE releasing EVIOCGRAB even on timeout. F24 was an invalid preliminary probe because the report descriptor limits usages to 0x65; disregard its missing evdev events.

High-speed with no_out_endpoint=1: host identified the gadget but SET_CONFIGURATION failed with -71, no input node appeared. Thus the workaround does NOT solve high-speed. A physical adapter fault is not established; DWC3/PHY/control-transfer diagnosis remains open. This is a configuration workaround candidate, not a verified kernel driver fix.

Candidate patch is opt-in, only applies when a HID function is newly created, and is NOT installed or included in production defaults. It removes the dedicated interrupt OUT endpoint, leaving keyboard output reports on endpoint zero. Existing gadget must be recreated to change the option. Full-speed needs separate max_speed configuration; no generic speed default change is proposed.

All test gadgets removed. Original keyboard, both mice, read-only Alpine ISO and fc400000 binding restored. Kiosk retained. Next priority: validate completed NUC Chromium before AV1 incremental rebuild.

## Follow-up on USB-A data connection

See `../hid-usba-20260922/README.md`: on test4 and the USB-A/hub host path,
high-speed works with both endpoint variants, including repeated input tests.
The earlier failure is connection/configuration-specific; do not enable the
workaround universally or diagnose the injector as defective from this test.
