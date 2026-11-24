# Green Cell UPS for Home Assistant (GC UPS App)

[Deutsch](README.de.md)

Home Assistant integration for **Green Cell UPS units** connected via USB to a PC that runs
the vendor's **GC UPS App**. The app has a built-in web server (Angular UI + JSON API); this
integration logs in to that API and polls it locally — no cloud, no NUT driver needed.

> Early beta. Not affiliated with Green Cell / CSG S.A.

## What you get

| Entity | Source |
|---|---|
| **Status** (online / on battery / battery low / self-test / fault / shutdown pending / UPS not connected) | derived, most severe first |
| Battery level, battery voltage | `batteryLevel`, `batteryVoltage` |
| Input / output voltage, input frequency | `inputVoltage`, `outputVoltage`, `inputFrequency` |
| Load (%) and **output power (W, estimated)** = load × rated power | `load`, spec `power` |
| Temperature (only if the UPS has a probe) | `temperature` |
| Mains power, On battery, Battery low, Charging, Fault, Shutdown pending | flags |
| Diagnostic: USB connection, self-test running, AVR active, beeper, rated power/VA, nominal voltages | |
| *Optional* buttons: battery self-test (10 s), toggle beeper | `POST /api/commands` |

"Charging" is derived, not reported: on mains, a 12 V lead-acid block sits at 13.5–13.8 V,
above the app's `batteryVoltageHighNominal`, and drops below it when discharging. The
"charging" label in the vendor UI is a fixed text.

Shutdown commands (`shutdownOrder`, `shutdownAndRestoreOrder`) and the long battery test are
**never** exposed. A smart home that can switch off the UPS it monitors is a risk.

## Requirements

1. The UPS is plugged into a PC (Windows or Linux) via USB, with the
   [GC UPS App](https://greencell.global/en/gcnews/premieres/latest-release-of-green-cell-ups-app)
   installed — or headless in Docker, see [fajfer/gcups](https://github.com/fajfer/gcups).
2. In the app: **Settings → enable HTTP server** (default port 8080) and set a password.
   Check in a browser: `http://<pc>:8080` shows the UI, `http://<pc>:8080/api/status` answers `1`.
3. Home Assistant 2025.2 or newer.

## Installation

**HACS:** ⋮ → Custom repositories → `https://github.com/marcbuetti/ha-greencell-ups`,
category *Integration* → install → restart HA.

**Manual:** copy `custom_components/greencell_ups` to `<config>/custom_components/` and restart.

Then *Settings → Devices & services → Add integration → Green Cell UPS*:

- **Host:** IP or name of the PC, optionally with port (`10.0.0.20` or `10.0.0.20:8085`)
- **Password:** the one from "Connect remotely" in the web UI. There is no user name.

Options: update interval (default 10 s) and *Allow control* (adds the two buttons).

## API notes (measured on a real installation)

```
GET  /api/status                 -> "1"   (no login)
POST /api/login {"password":…}   -> 201 {access_token}   (JWT)
GET  /api/current_parameters     Bearer
GET  /api/nominal_parameters     Bearer
GET  /api/device/specification   Bearer
GET  /api/data                   Bearer   manufacturer, vendor, protocol, info
POST /api/commands {"action":"shortTestOrder","args":{}}   Bearer
```

- **The login body schema is strict.** An extra field such as `username` gives **403**, a
  wrong password **401**. Don't read a 403 as "wrong auth method".
- Field names over HTTP are **camelCase** (`batteryLevel`, `utilityFail`); the snake_case
  names in the UI bundle are route names. Both are accepted.
- **`offline: true` is not a fault.** It describes the topology (line-interactive instead of
  double conversion) and is `true` in normal operation.
- **Negative numbers mean "unknown"**: `-1` without a temperature probe or USB link → shown
  as *unknown*, never as "−1 °C". `0` stays valid (0 V input = no mains).
- Without USB (`connected: false`) the app reports placeholders like `failed: true` and
  `shutdownActive: true`. The integration then shows **Status = UPS not connected** and
  marks all measured entities unavailable — no false alarm, no plausible-looking zeros.
- The token is kept until rejected; then the integration logs in again and retries **once**
  (survives app restarts, which silently invalidate tokens).

## Green Cell UPS with network instead of USB?

Checked (Nov 2026): Green Cell does not sell a UPS or network card that serves this API
directly. The API comes from the GC UPS App (Electron + Express) on the PC, not from the UPS.
Green Cell's rack/RTII line is not documented with an SNMP slot either; if a model with a
network card shows up, it would most likely speak SNMP, not this API (→ use HA's SNMP or NUT
integration for that). Ways to get the UPS "on the network" with this integration:

- any always-on PC/NAS/VM with USB passthrough running the GC UPS App,
- a Raspberry Pi / Linux box with the Docker image [fajfer/gcups](https://github.com/fajfer/gcups).

Alternatively, many Green Cell models work with NUT (`nutdrv_qx`), see the
[NUT hardware list](https://networkupstools.org/ddl/Greencell/PowerProof_2000.html).

## Troubleshooting

- *Cannot connect:* PC asleep, HTTP server not enabled in the app, firewall on port 8080.
- *Password rejected:* the app answers 401 — check the password in the web UI.
- *Everything unavailable, status "UPS not connected":* the app runs but does not see the UPS
  on USB (cable, driver, wrong USB device in Docker).
- Check from a shell, without storing the password in history:
  `GCUPS_HOST=10.0.0.20 GCUPS_PASSWORD=… python tools/probe.py` (read-only).

## Development

```bash
pip install aiohttp pytest pytest-asyncio
python -m pytest tests
```

MIT License.
