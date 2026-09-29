# Profil G: lokaler Bildschirm- und Audioempfänger

## Ausgangspunkt

Testzweig: `feature/profile-g`
Basis: `ci/adf-compare-20260927`, Commit
`dba06ef52ebcb081e4e2725ab9b17a90c25f0671` (2026-09-28).

Dieser Zweig übernimmt den vollständigen versionierten A–D/F-Teststand,
einschließlich der optionalen CPU-Speicherkopie, CLI-Auswahl und begrenzten
Konvertierungs-Wiederherstellung. Die Basis ist ein Teststand, keine vollständige
Freigabe. Unversionierte Buildartefakte und temporäre Dateien werden nicht
kopiert; Binärdateien müssen wie bisher über die Build-Eingaben bezogen werden.

## Zweck und Abgrenzung

G empfängt Bild und Ton eines Rechners oder Mobilgeräts und gibt sie über HDMI
am TV/Monitor aus. Ziel ist geringe Ende-zu-Ende-Latenz im lokalen Netzwerk.
Profil E bleibt dem Fernzugriffsclient für IT-Fernwartung vorbehalten; F bleibt
der lokale Browserkiosk. Anzeige-, Audio- und Decoder-Komponenten sollen
wiederverwendet werden. Bestehende A–D/F-Standardpfade bleiben erhalten.

Kandidaten: AirPlay (UxPlay), Miracast, Moonlight mit Sunshine als Sender,
Steam Link sowie nach Machbarkeitsprüfung Google Cast und weitere Empfänger.
AirPlay, Moonlight und experimentelles Miracast sind inzwischen als erste
Implementierung vorhanden; siehe [Implementierung und Tests](IMPLEMENTATION.md).
Kurze Live-Tests von Miracast und Moonlight wurden mit Bild und synchronem Ton bestätigt; eine vollständige Freigabe steht aus. Miracast benötigt einen eigenen WLAN-/Wi-Fi-Direct-Test und
kann mit dem Router-AP auf derselben Funkkarte konkurrieren.

## Testplan

1. Vorhandene Anzeige-/Audio-/Decoder-Basis erfassen und reproduzieren.
2. Empfänger einzeln und reversibel testen, zunächst 1080p60 über LAN, danach
   WLAN, soweit das Protokoll diese Wege unterstützt.
3. Ende-zu-Ende-Latenz, Bildrate/Frame-Pacing, Bildqualität, Audio-Synchronität,
   Ressourcenverbrauch und Senderkompatibilität vergleichen.
4. Bildschirmbesitz und Wechsel zwischen Kiosk und Empfänger definieren;
   Eingaberückkanal nur bei unterstützten Protokollen anbieten.
5. Native CLI, optionale Pakete und reproduzierbaren G-Testbuild ergänzen,
   anschließend Installation und Update inklusive Konfigurationserhalt prüfen.

## Spätere Übernahme nach main

- G-Änderungen in separaten, fachlich begrenzten Commits entwickeln.
- Gemeinsame Fehlerkorrekturen zuerst im zuständigen A–D/F-Zweig festhalten und
  hier übernehmen; keine abweichenden Kopien gemeinsamer Komponenten pflegen.
- Vor Integration den dann aktuellen main-Stand abgleichen und bestehende
  A–D/F-Tests zusätzlich zu G ausführen. Konflikte fachlich lösen, nicht pauschal
  mit einer Zweigversion überschreiben.
- Wenn die A–D/F-Basis nach main übernommen ist, G darauf aktualisieren und den
  verbleibenden G-Diff als eigene Änderung prüfen. Bei abweichender Historie
  (z. B. Squash-Merge) nur die G-Commits auf main übertragen.
- Ungeprüfte G-Funktionen nicht als Standard aktivieren. Release-Watcher und
  öffentliche Standard-Builds erst nach gesonderter Freigabe erweitern.

Der G-Testworkflow prüft die Richtlinien und baut die drei Empfänger sowie ein
ladbares ARM64-Containerimage auf einer per Prüfsumme verifizierten F-Basis.
Das Artefakt `profile-g-runtime-arm64-<Run-ID>` enthält `runtime.tar`, Metadaten
und Prüfsummen. Es ist kein SD-/ISO-Image und verändert kein Livesystem.

Moonlight verwendet für `codec h264` mit `decoder auto` oder `hardware` die
privat eingebauten V4L2-Request-Bibliotheken. `auto` erlaubt Moonlights
Software-Rückfall; `hardware` verlangt Hardware. `decoder software` sowie
andere Codecs behalten die Distributionsbibliotheken. Miracast/AirPlay laden
weiter ihre GStreamer-Bibliotheken. AirPlay/UxPlay ist enthalten; der Test mit
einem Apple-Sender folgt nach Prüfung dieses Containerbuilds.


## Gemeinsames A–D/F/G-Testimage

`profile-g-image.yml` baut zusätzlich ein vollständiges SD-Image (`.img.xz`)
und eine Update-ISO. Die bestehende A–D/F-Zusammenstellung wird einschließlich
Chromium, Sunshine, nativer CLI und optionalem Panthor-Testkernel übernommen.
G verwendet den erfolgreichen parallelen Containerbuild **desselben Commits**;
ein fehlgeschlagener oder älterer Lauf darf nicht eingesetzt werden.

Der G-Container wird getrennt vom Kiosk offline bereitgestellt und beim Boot
importiert, jedoch nicht automatisch gestartet. Persistente Konfigurationen
und Pairings werden nicht in das Image kopiert oder beim Import geändert.
Die ISO-Installation und Zustandserhaltung müssen danach am ROCK separat
geprüft werden. Der Build greift nicht auf das Livesystem zu.

Die Inhaltsprüfung muss beide Runtimearchive, CLI-Eigentümer, Profile im
Manifest, Kernel/DTB/Initramfs, Firmware, CPU-Kopierhilfe und alle bisherigen
A–D/F-Prüfungen bestätigen, bevor SD/ISO als Artefakte hochgeladen werden.
