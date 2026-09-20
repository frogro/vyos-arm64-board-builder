# Agreed profile F delivery policy — 2026-09-20

Requirements agreed with the user; not yet a completed implementation.

## Sequence

1. Finish and validate the native container kiosk CLI: URL, output, rotation.
2. Add limited Sunshine administration: enable/disable remote access without
   stopping the local kiosk, require encryption, pair/revoke clients, show status,
   and recover administrative credentials. Reuse VyOS authorization. Permanent
   settings use commit/save; one-time pairing uses operational commands.
3. Package defaults, runtime helpers and migrations in profile F fresh-install
   and update artifacts; validate both paths on hardware.

## Generic first-install defaults

- Rotation 0 (landscape); dynamically select a connected display.
- Streaming audio off, LAN/WAN encryption required, UPnP off.
- Web administration local-only, accessible through an SSH tunnel.
- Discover encoder capabilities; MPP only on compatible hardware.
- No fixed lab IPs, HDMI names, USB IDs or shared credentials.
- Moonlight bitrate/resolution/FPS remain client choices.
- Initial remote-access activation and credential provisioning still need design.
- Do not automatically open WAN firewall ports.

## Configuration ownership and updates

Saved VyOS configuration owns CLI-managed settings. Preserve other supported
Sunshine options edited via the web interface. Do not overwrite the whole
Sunshine file or automatically import arbitrary web edits into VyOS.

Initialize defaults only for new installations or genuinely absent settings;
never overwrite administrator values, including explicit off/false. Preserve URL,
orientation, selected output, Sunshine settings, pairing state, certificates and
browser state across image updates and container replacement. Include helpers in
the image; live-only files under /etc and /usr/local are insufficient.

Use versioned, idempotent migrations with backups and documented rollback.
Before claiming update support, test fresh installation, update with modified
settings (including portrait), retained pairings/certificates/web-only options,
reboot, repeated migration and rollback compatibility. Persistent storage alone
does not establish a working update path.
