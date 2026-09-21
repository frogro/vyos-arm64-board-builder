# Profil F: Ergebnisse der Nacht zum 21.09.2026

## Laufendes System

ROCK läuft mit 6.18.50-vyos-f-test2 und dem bisherigen Kiosk-Image
localhost/vyarm-kiosk:touch-reconnect-20260920. Dienst aktiv, keine fehlgeschlagenen
Units beim Abschluss. Modem, Release-Workflows und main unverändert. Keine Commits
gepusht. Test2 war ein einmaliger Boot; der normale Bootstandard bleibt der alte
Kernel. Nicht versehentlich eine dauerhafte Kernelumstellung voraussetzen.

## Nachgewiesen

- Mali-Rendering im tatsächlichen Kiosk-Chromium mit unveränderten Startflags und
  Sandbox, inklusive korrektem WebGL-Testpixel. Automatische Software-Rückkehr bei
  absichtlich fehlerhaftem Grafikstart ebenfalls getestet.
- Gebündeltes Runtime-Image mit generischer Grafikoption software/auto,
  begrenzter Render-Gruppenfreigabe und getrennten Grafik-/Browser-Caches getestet.
- H264 und HEVC erzeugen gültige 1080p-Bitstreams; unabhängige Dekodierung und
  Grauwerteprüfung bestanden. Keine Aussage über reale Moonlight-Latenz daraus.
- Zwei experimentelle FFmpeg-Korrekturen vermeiden mehrfaches EOS-Einreihen und
  doppelte Freigabe noch bei MPP liegender Frames beim Abbruch. 68 Tests mit
  regulärem Ende, kurzen/leeren Streams und Abbruch ohne Speicherpoolwarnungen.
- Vollständiges Sunshine-Testimage mit diesen Korrekturen gebaut; tatsächliche
  Sunshine-Encoderprüfung für H264/HEVC erfolgreich. Weitere 50 Sitzungen je Codec
  im selben Prozess ohne diese Warnungen; kurze RSS-/FD-Messung ohne fortlaufend
  steigende Spitzen. Das ist kein Dauerbetriebsnachweis.

Aktueller separater Testkandidat:
`localhost/vyarm-kiosk:cleanup-candidate-20260921`
Image-ID `3fac48e2a9b718d0347acfa997196486963df120546a8339c4b0017fd42b6005`
Quellrevision des Build-Rezepts: `6b5d831`.
Die bisherigen Live-Settings und Pairings wurden hierfür nicht ersetzt.

## Noch offen

1. Echter Moonlight-H265-Test mit Verbinden/Trennen und subjektiver Bedienung,
   Hochformat, Touch und Audio-Policy. Dafür den Kandidaten kontrolliert mit
   Sicherung und unabhängigem Rollback aktivieren.
2. Die experimentellen Cleanup-Patches sind im separaten Testrezept enthalten,
   noch nicht im normalen F-Rezept. Fehlerszenarien und echte Streaming-Sitzungen
   vor dieser Übernahme prüfen.
3. Neues CLI-Debianpaket bauen/installieren: Quellen, XML-Schema und Completion
   geprüft; lokaler Docker-Bau wartet weiterhin auf die angebotene sudo-Sitzung.
4. RGA BT709/Wertebereich bleibt fehlerhaft; CPU-Konvertierung bleibt aktiv.
5. Video-Hardwaredekodierung erfordert mehr als einen Kernel-Schalter: Im
   Testbaum fehlen RKVDEC2-Quelldateien und Decoder-DT. Ein vollständiger Decoderport
   samt Userspace und anschließend eigener Chromium-Mediaprüfung steht aus.
6. Vollständiges reproduzierbares F-Installations-/Update-Image inklusive Offline-
   Container-Provisionierung, Kernel-Auswahl und echten Installations-/Updateboots.

Die Nachtmessungen ersetzen keine physische Touch- oder Audioprüfung. Hardware-
WebGL, Video-Encoding und Video-Decoding sind getrennte Fähigkeiten.

Details und Rohdaten: sunshine/hevc/README.md, sunshine/decoder-investigation/README.md,
sunshine/rga-investigation/README.md und BUILD-INTEGRATION.md.
