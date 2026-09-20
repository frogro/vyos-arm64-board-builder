# CMS and native API boundary — initial assessment, 2026-09-20

Hardware testing paused at user's request (touch monitor battery empty).
Portrait, local touch, native container restart and complete ROCK reboot passed;
see CLI.md for evidence, remaining warnings and image-update limitations.
No further live changes for CMS research.

Keep profile F a URL-driven kiosk. Customer owns website/content/CMS. Preferred
architecture: external CMS publishes a stable HTTPS display URL; Chromium keeps
that URL open and the webpage/player refreshes content on schedule. Breakfast,
lunch and evening transitions belong to the CMS/player, not repeated router
configuration commits. Define refresh/push, timezone and offline fallback when
validating an actual CMS; a static webpage does not update itself automatically.

Optional management integration uses the existing native VyOS HTTPS API to set
container environment/configuration, ultimately the planned native kiosk schema.
This is a proposed use of the native configuration API, not a tested or enabled
kiosk API. No `service kiosk` node exists yet. Do not put router API credentials
in the displayed webpage. Use a trusted management backend over an authenticated,
TLS-verified management connection. CMS accounts are not router admin accounts.
No new custom router permissions subsystem is proposed.

Candidates (not installed or validated):
- Xibo: self-hosted open-source CMS, documented Dayparting explicitly covers
  breakfast/lunch/dinner and weekday exceptions. Strong functional fit for menu
  boards. Requires a compatible signage player; ordinary Chromium with a CMS
  administration URL is not equivalent. ARM64/player/browser suitability needs
  verification. Hosting/maintenance and commercial player/add-on costs must be
  distinguished from free CMS licensing.
- Concerto: free open-source web-based signage, browser display approach. Candidate
  for keeping current Chromium container. Recurrent restaurant daypart scheduling,
  maintenance status and current Chromium compatibility need evaluation.
- Anthias: free signage with web assets, schedules and REST API, but brings its own
  player/device stack; not assumed to be a drop-in external CMS for this kiosk.

Sources checked:
https://xibosignage.com/open-source
https://xibosignage.com/pricing
https://account.xibosignage.com/manual/en/scheduling_dayparting
https://account.xibosignage.com/docs/setup
https://www.concerto-signage.org/overview
https://anthias.screenly.io/
https://docs.vyos.io/en/rolling/automation/vyos-api.html

## Xibo browser-player follow-up

Documentation review found a concrete browser integration candidate, correcting
any blanket implication that Chromium cannot be used with Xibo:
https://github.com/xiboplayer/xiboplayer-chromium
This independent community project (explicitly unaffiliated with Xibo Signage
Ltd) bundles a web/PWA player, a local Node.js CMS proxy, and launches system
Chromium on localhost:8766. Its organization lists Chromium packages as noarch,
PWA for modern browsers, and separate Electron/arexibo aarch64 packages:
https://github.com/xiboplayer
These are project claims, not tested ROCK/container compatibility. The old
standalone xiboplayer-pwa repository is archived; use current maintained sources
and resolve dependency versions rather than selecting that archive blindly.

Official legacy Linux player documentation targets AMD/Intel 64-bit and cannot
be used to rule out these independent ARM/browser implementations. Official
installation docs also announce a new-generation Linux player under development:
https://account.xibosignage.com/docs/setup/xibo-for-linux-installation
https://account.xibosignage.com/docs/setup/can-i-run-a-xibo-player-on-my-raspberry-pi-all-variants

Candidate test architecture: external Xibo CMS -> community web player/proxy ->
existing Chromium kiosk. No routine VyOS API calls for content schedules. First
review pinned sources, CMS compatibility, credential handling and offline cache;
then test images, recurring schedules, portrait and existing Sunshine session in
an isolated container variant. No installation or live changes performed.

Optional smaller alternative accepted by user: supply a simple image slideshow
web application with interval/time-window controls; customer supplies the images.
This is an optional companion, not a requirement for arbitrary customer URLs.
