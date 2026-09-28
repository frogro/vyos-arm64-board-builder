# Receiver research, 2026-09-28

## Decisions linked to upstream evidence

- [UxPlay upstream](https://github.com/FDH2/UxPlay): GStreamer video/audio sinks,
  decoder selection, PIN registration and persistent key files allow an
  independent receiver with durable /state. Source pinned at
  8f40118b1a72d7e16ce684b0f3ce6a0ae32bdc79. Start with H264 mirroring; do not
  transfer Chromium-specific buffer switches to unrelated decoder stacks.
- [Moonlight Qt upstream](https://github.com/moonlight-stream/moonlight-qt) and
  [CLI implementation](https://github.com/moonlight-stream/moonlight-qt/blob/8369d1a0e11b999d4d1598f62ca5f6dea49602fb/app/cli/commandlineparser.cpp):
  use the actual stream/host/app options, codec names and decoder choices.
  Build from 8369d1a0e11b999d4d1598f62ca5f6dea49602fb including pinned submodules.
- [MiracleCast upstream](https://github.com/albfan/miraclecast): explicit
  --interface, sinkctl run LINK and external-player support. Source pinned at
  0b7f1f1f6586dc65ff480f3cda5c2170a70aa020. Avoid the upstream quick-start's global
  shutdown of network services on a router. Replace the example player's
  unlimited queues with bounded queues; run media playback unprivileged.
- [Maintainer discussion #271](https://github.com/albfan/miraclecast/issues/271)
  and [report #529](https://github.com/albfan/miraclecast/issues/529): a Wi-Fi
  Direct connection is not by itself a successful Miracast stream; Samsung
  source behavior needs a real SmartView/DeX test. Reports motivate tests,
  not unconditional driver changes.
- [MediaTek mailing-list P2P support patch](https://lists.infradead.org/pipermail/linux-mediatek/2023-January/054250.html):
  MT7921 P2P client/GO support explicitly accounts for firmware connection
  types. [Channel-context discussion](https://lists.infradead.org/pipermail/linux-mediatek/2022-August/047100.html)
  documents concurrent-role complexity. [MT7925 P2P fix discussion](https://www.spinics.net/lists/linux-wireless/msg260540.html)
  shows that P2P is a supported but evolving path. Inspect the running PHY;
  don't add historical patches blindly to our newer kernel.
- [Valve Raspberry Pi instructions](https://help.steampowered.com/en/faqs/view/6424-467A-31D9-C6CB)
  document a Pi deployment, not tested RK3588 support.
  [Valve developer forum reply](https://steamcommunity.com/app/353380/discussions/6/4697909023281926501/)
  points to newer Pi 5 beta support: old forum claims of no ARM64 support must
  not be generalized. [2026 native ARM64 report](https://steamcommunity.com/app/353380/discussions/10/571544346711605626/)
  reports decoder integration failures on another SoC, not a ROCK result.
  Keep Steam Link unadvertised until a suitable distributable runtime is tested.
- [Google receiver model](https://developers.google.com/cast/docs/overview):
  a Web Receiver runs on a Cast-enabled device; an ordinary Chromium page is
  not equivalent to a Chromecast receiver. No working G implementation claimed.

All of these are external technical references, not instructions to change
router network ownership or disable existing services.
