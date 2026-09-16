# ROCK 5B live validation — 2026-09-16

Running image: 999.202609160043; boot ID 66905f8a-6812-4334-a949-baa1b06335e8.
Repository changes remain a candidate; this is not validation of a rebuilt image.

## Passed

- Quectel native WWAN unattended warm reboot, DHCP and three interface-bound
  Internet pings. Ethernet remains the primary default route.
- Tailscale Running, health list empty; KVM services active; zero failed units.
- Local RTSP H.264 1920x1080: 301 video packets in a five-second ffprobe interval,
  reported 60 fps. This does not measure browser latency or WAN performance.
- Wired DHCP/SSH setup repeated live successfully with existing settings.
- AP setup repeated live: AP, DHCP, SSH and Ethernet WAN checks pass.
  Only prior wireless hw-id removed, as intended by dynamic PHY binding.
  No other configuration delta. Wireless client traffic was not retested.
- Locale setup repeated live with unchanged native settings, Chrony synchronized.
- Fourteen focused regression suites for modem, KVM, Tailscale, image validation
  and HDMI audio passed, plus common-firstboot packaging and five setup-helper tests.

## Helper corrections

- Checked configuration commands, no-change commit handling, save error propagation.
- AP replacement limited to selected/prior cached interface; preserve other WLANs,
  DNS forwarding entries and unselected NAT rules. The setup still owns its selected
  DHCP network, NAT rule and fixed AP/WAN firewall chains/rules; review these on
  an already customized deployment.
- UTF-8 defaults are image-owned and preserve unrelated environment entries.
  Timezone, keyboard and radio country remain independent native settings.
- Administrative executable paths work for non-login SSH invocation too.
- First-boot DHCP wrapper waits for mounted /config and completed VyOS startup.
  Its new boot wait is packaged/syntax checked, not a fresh-install hardware test.

## Remaining journal findings

- Rsyslog first start failed, then succeeded ten seconds later; generated runtime
  configuration timestamp matches the successful retry. Current rsyslog config
  validation passes. Boot ordering race suspected, initial stderr not captured;
  no speculative logging-unit override applied.
- Early Rockchip supply deferral/device-link errors; deferred-device list later empty.
- MPP probes report unavailable codec clients; active H.264 encoder works.
- HDMI allocation message diagnosed and capture-buffer limit tested below.

## HDMI DMA allocation diagnosis

The HDMI Device Tree reserves a 160 MiB non-reusable shared DMA pool below 4 GiB.
It is present and assigned, although /proc/meminfo reports CmaTotal=0: this is
not a reusable CMA allocation. CONFIG_DMA_CMA being unset is not proof that this
reserved pool is missing.

The pinned ffmpeg-rockchip v4l2 source requests 256 MMAP buffers. Each 1080p BGR24
frame is 6,220,800 bytes, page-aligned to 6,221,824. The reserved coherent allocator
uses power-of-two page blocks (8 MiB each here). Twenty fill 160 MiB. The next
allocation fails, producing the journal message; vb2 returns the successfully
allocated count. /proc/<ffmpeg-rockchip>/maps confirms exactly 20 video0 mappings.
FFmpeg accepts the reduced count and streams normally.

Fix direction: bound capture-buffer requests for the HDMI backend, expose a
supported FFmpeg option if necessary and verify at 1080p and higher resolutions.
Do not enlarge reserved RAM or suppress kernel errors just to hide this message.

Sources:
- https://github.com/nyanmisaka/ffmpeg-rockchip/blob/d90e3a1c18d7929383cf88c1b3da2e2d1c966cbf/libavdevice/v4l2.c
- https://github.com/torvalds/linux/blob/v6.18/kernel/dma/coherent.c
- https://github.com/torvalds/linux/blob/v6.18/drivers/media/common/videobuf2/videobuf2-core.c

## Still requires hardware/image validation

FM350 USB data path with rebuilt rndis_host-enabled kernel and mbimcli packaging;
new image upgrade/fresh-install behavior; cold boot without RTC battery; CSI hardware;
physical modem-port power switching. No new build started by this audit.

## HDMI buffer correction validation

The pinned FFmpeg build now includes an optional `capture_buffers` V4L2 option
(default remains 256). The runner requests four buffers only when the selected
source is internal RK3588 HDMI-RX. USB sources retain their upstream default.
Both media build and image install verify the new option is present. The applied
source patch is shipped alongside the original source archive for reproducibility.

Live policy test on the old binary used a temporary, driver-scoped ioctl interposer
under /run systemd configuration. It was removed after the test; it is not shipped.
Two stream starts used exactly four mapped buffers and produced no DMA allocation
errors. A 15-second RTSP sample contained 901 video packets at reported 60 fps;
a separate ten-second decode completed without reported decoder errors (569 frames,
including initial acquisition). This validates the buffer policy at 1080p, not the
newly compiled binary or 4K operation. Existing live binary restored afterwards.

All 39 local test commands from the image workflow passed. The real patched FFmpeg
compilation and new-image boot tests remain CI/hardware acceptance steps.

## Native failover/failback — 11:32 local time

Controlled live test administratively lowered eth0 using `ip link set eth0 down`.
An independent systemd recovery timer was armed before disconnecting management;
it was cancelled after successful automatic restoration, without executing.
No persistent VyOS configuration changes or custom failover daemon were used.

- Baseline: default via Ethernet, 3/3 pings to 1.1.1.1.
- eth0 down 11:32:10: first route lookup already selected wwan0, 5/5 pings,
  average 26.8 ms (first 72 ms; following 12.7–17.7 ms).
- eth0 up 11:32:14: Ethernet default observed at 11:32:20 (two-second sampling),
  5/5 pings, average 8.2 ms.
- Both native DHCP clients, Tailscale and KVM video remained active at completion.

This verifies router-originated connectivity after interface-down failover and
failback using native route distances 1/200. It does not establish uninterrupted
TCP/KVM sessions, forwarded WLAN-client failover, or detection of upstream Internet
loss while the Ethernet link remains up.
