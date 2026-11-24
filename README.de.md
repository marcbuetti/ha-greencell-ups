# Green Cell USV für Home Assistant (GC UPS App)

[English](README.md)

Integration für **Green-Cell-USVs**, die per USB an einem PC mit der **GC UPS App** hängen.
Die App bringt einen Webserver mit (Angular-Oberfläche + JSON-API); die Integration meldet
sich dort an und fragt lokal ab — ohne Cloud, ohne NUT.

> Frühe Beta. Keine Verbindung zu Green Cell / CSG S.A.

## Was es gibt

- **Status**: Netzbetrieb / Akkubetrieb / Akku schwach / Selbsttest / Störung / Abschaltung
  läuft / USV nicht verbunden (USB)
- Akkustand, Akkuspannung, Ein- und Ausgangsspannung, Netzfrequenz, Last, **Ausgangsleistung
  (geschätzt: Last × Nennleistung)**, Temperatur (nur mit Fühler)
- Netzspannung, Akkubetrieb, Akku schwach, Lädt, Störung, Abschaltung läuft
- Diagnose: USB-Verbindung, Selbsttest läuft, AVR aktiv, Signalton, Nennwerte
- *Optional* (in den Optionen „Steuerung erlauben"): Akku-Selbsttest (10 s), Signalton umschalten

Abschaltbefehle und der lange Akkutest werden **nie** angeboten.

## Voraussetzungen

1. USV per USB am PC (Windows/Linux) mit installierter GC UPS App — oder ohne Bildschirm
   im Docker-Container, siehe [fajfer/gcups](https://github.com/fajfer/gcups).
2. In der App **Einstellungen → HTTP-Server einschalten** (Port 8080) und Passwort setzen.
   Test: `http://<pc>:8080/api/status` antwortet `1`.
3. Home Assistant ab 2025.2.

## Einrichtung

HACS → Benutzerdefinierte Repositories → `https://github.com/marcbuetti/ha-greencell-ups`
(Integration) → installieren → HA neu starten → *Integration hinzufügen → Green Cell UPS*.
Host = IP des PCs (optional `:Port`), Passwort = das aus „Connect remotely". Einen
Benutzernamen gibt es nicht.

## Fallen der API (am echten Gerät gemessen)

- Login-Körper mit einem zusätzlichen Feld (z. B. `username`) → **403**; falsches
  Passwort → **401**.
- Über HTTP kommt camelCase (`batteryLevel`, `utilityFail`), nicht die snake_case-Namen aus
  dem JavaScript.
- `offline: true` ist **keine Störung**, sondern die Bauart.
- Negative Werte = „weiß ich nicht" → *unbekannt*. `0` bleibt gültig.
- Ohne USB (`connected: false`) liefert die App Platzhalter (`failed: true` …). Dann steht
  der Status auf „USV nicht verbunden" und alle Messwerte sind *nicht verfügbar* — kein
  Fehlalarm.

## USV mit Netzwerk statt USB?

Geprüft (Nov. 2026): Eine Green-Cell-USV oder Netzwerkkarte, die diese API selbst anbietet,
gibt es nicht. Die API stammt aus der GC UPS App auf dem PC, nicht aus der USV. Eine
künftige Netzwerkkarte würde eher SNMP sprechen (→ SNMP- oder NUT-Integration). Ins Netz
bringt man die USV mit einem dauerhaft laufenden PC/NAS/VM mit der App oder einem
Raspberry Pi mit dem Docker-Image [fajfer/gcups](https://github.com/fajfer/gcups).

## Fehlersuche

Lesend prüfen, ohne Passwort in der Shell-History:
`GCUPS_HOST=10.25.14.4 GCUPS_PASSWORD=… python tools/probe.py`
