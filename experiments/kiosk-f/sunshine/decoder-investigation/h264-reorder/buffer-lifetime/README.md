# V4L2 buffer reuse measurements

2026-09-21, isolated Chromium153 on Weston16/test3. Two runs per fixture,
second pair in reversed order. First baseline overlapped the final Brave
image build; the independent reversed repeat confirms the same pattern.
A private tracefs instance records only QBUF/DQBUF for video minor2. No
production tracing configuration changed; instance removed after each pair.
All four traces have zero overrun/commit-overrun/dropped-events. Reduced
CSV preserves timestamp, event, index and queue type. Stats retained.

| Metric | Pyramid first / repeat | No-pyramid first / repeat |
|---|---|---|
| HTML drops/1800 |268 /262|8 /8|
| CAPTURE QBUF and DQBUF counts |1800 each|1800 each|
| QBUF→DQBUF median ms |3.205 /3.207|3.156 /3.143|
| DQBUF→next same-index QBUF p95 ms |169.814 /169.976|148.392 /148.212|
| Consecutive QBUF interval p95 ms |33.821 /33.876|18.436 /17.957|

Each run ended; V4L2VideoDecoder/platform=true. All1800 capture buffers were
returned, not evidence of pixel correctness. QBUF→DQBUF includes driver and
userspace scheduling and is NOT pure hardware decode time. DQBUF→QBUF
includes codec references, renderer retention, free time and scheduling;
it does NOT measure only time blocked on references. Queue gaps remain
correlated with pyramid structure, not proof that buffer count is the cause.
Codec DPB and display reorder requirements change together in these fixtures.

`summarize.py file.csv` regenerates statistics. `first-run.sh` and
`repeat-run.sh` use the existing browser harness copied into tools/ with
its codec list limited to h264. Device minor2 must be revalidated on other
hardware; this experiment is not a product rule identifying a board.

## Additional Chromium instrumentation — NOT BUILT

chromium-lifetime-instrumentation.patch adds media trace events to the
active V4L2StatelessVideoDecoderBackend (not the separate newer stateless
backend): free input/output availability, surface pause and reuse callback.
Only source-context application checked. No compilation or live validation,
no production packaging. A Chromium build plus preservation of these events
in the CDP trace collector is needed before claiming userspace lifetime proof.
Use with device trace to distinguish driver completion, codec/renderer-held
frames and actual decoder starvation. Do not change buffer counts based only
on current timing correlations.
