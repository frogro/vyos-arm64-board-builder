# Retrospective hang review — 2026-09-22 18:35 CEST

Read-only review of retained ROCK journals, browser artifacts, test harness and
saved kernel streams. No new decode run, reboot or live configuration change.

## Last unexpected interruption

- First hardware AV1 auto run reached EOS,1800 frames/22 presentation drops.
  Results written17:40:54 CEST.
- Software result file created17:40:58, remains empty. Its stderr proves the
  test page and video request at17:41:02, last favicon request17:41:03. These
  HTTP timestamps are UTC15:41, not local15:41. No actual decoder property was
  retained for this interrupted run; software was requested by the harness.
- Retained journal ends17:40:54; next boot journal begins17:43:17. No retained
  kernel panic, OOM, USB disconnect or decoder timeout proves the cause.
  User-manager shutdown.target at17:40:54 is session exit, not host shutdown.
- The harness arms a temporary watchdog (30s, keepalive every2s, total480s)
  and8minute reboot timer. A reset via either guard is possible, but no retained
  guard firing/reset-cause record establishes which mechanism reset the board.
- Software decode still uses GPU/Wayland/DRM. AV1 driver also remains loaded
  between auto/software tests. Neither pure CPU isolation nor AV1 causation
  follows from the software label. Investigate hardware-session teardown,
  runtime PM and graphics start/stop separately with an external kernel stream.

## Separate confirmed display fault burst

Combined candidate boot log records1850 VOP IOMMU read faults at17:49:29–44,
50 POST_BUF_EMPTY messages17:49:34–55, one BUS_ERROR17:49:58 and a vblank
warning17:49:30. Counts are retained messages, not necessarily all events.
Provider fdd97e00 is display VOP, not AV1 VSI fdca0000. PTE valid0 is logged;
stack goes through drm_atomic_helper_dirtyfb and drm_fb_helper_damage_work.
This points to display framebuffer mapping/commit lifecycle as a concrete
investigation target. It occurred before AV1 module registration17:51:05,
so is not an AV1 decoding failure in that run. Causation for the preceding
17:41 interruption is unproven. Later combined browser comparisons all reachEOS.

## Controlled failures and current state

The retained decoder watchdog timeouts17:34–35 and17:57:54 are intentional
completion-withholding injections, with recovery/reference tests passing.
Do not classify these as spontaneous recent decoder hangs.
Current restored test4 kernel has no newly recorded matching fault burst.
Earlier USB disconnects21Sep20:06/21:21 and22Sep03:19 lack a temporal link to
this interruption. Empty pstore does not rule out a panic or power loss.

Next bounded diagnostic should capture externally, compare software-only with
AV1 never loaded against hardware→teardown→software, and separately inspect
VOP framebuffer ownership/mapping. Keep the known boot panic=30/kexec setup
error distinct. No full kernel promotion based on the current evidence.
