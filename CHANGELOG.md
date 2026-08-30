# Changelog

Alle relevanten Änderungen an der gPlug Energy Integration werden in dieser Datei dokumentiert.

Das Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/)
und dieses Projekt folgt [Semantic Versioning](https://semver.org/lang/de/).

## 1.3.0
- **Quality Scale: Silber**
  - Vollständige Testsuite: 67 Tests, 100 % Coverage über alle Module (Config Flow, MQTT-/HTTP-Sensorik, Energy-Dashboard-Automatik, Diagnostics), in der CI mit ≥95 % erzwungen
  - `PARALLEL_UPDATES` deklariert, `data_description`-Texte für alle Formularfelder (de/en/fr/it)
  - README: Parameter-Tabelle und Entfernen-Anleitung
- **Fix**: Nicht-numerische Messwerte (z. B. "n/a" vom Zähler) werden als unbekannt gemeldet statt numerische Sensoren beim State-Write crashen zu lassen

## [1.1.1] – 2026-03-26

### Hinzugefügt
- **Optionen für Auto-Konfiguration**: Energy Dashboard und Lovelace-Karte können jetzt unter Einstellungen → Geräte & Dienste → gPlug Energy → Konfigurieren ein-/ausgeschaltet werden
- Beide Optionen sind standardmässig aktiviert (wie bisher)
- Wer die Konfiguration manuell machen möchte, kann die Automatik deaktivieren
- Optionen wirken sofort nach HA-Neustart

## [1.1.0] – 2026-03-26

### Hinzugefügt
- **Alle gPlug Produkte unterstützt**: gPlugD, gPlugD-E, gPlugK (Kamstrup), gPlugM (M-Bus)
- **Auto-Model-Detection**: Gerätemodell wird automatisch aus dem MQTT-Topic erkannt (z.B. `tele/gPlugK_ABC123/SENSOR` → Modell: gPlugK)
- **Produkt-Übersicht im README**: Tabelle mit allen Modellen, Schnittstellen, kompatiblen Smart Metern

### Geändert
- `_build_device_info()` erkennt jetzt das Modell automatisch statt immer "gPlugD" zu setzen
- README: Voraussetzung und Architektur sind jetzt modell-unabhängig formuliert

## [1.0.9] – 2026-03-26

### Geändert
- **Branding korrigiert**: Firma = gPlug, Produkte = gPlugD/gPlugD-E/gPlugM/gPlugK
- Integrations-Name, Config Flow, Lovelace-Karte, Logs verwenden „gPlug" (Firma)
- Produkt-spezifische Referenzen (MODEL, Gerätename, MQTT-Topic, Architektur) bleiben „gPlugD"
- Repo-URL: `ha-gPlug-energy`

## [1.0.8] – 2026-03-25

### Geändert
- Repo umbenannt auf `ha-gPlugD-energy` (wurde in v1.0.9 wieder korrigiert)
- `CARD_VERSION` mit `manifest.json` Version synchronisiert

## [1.0.7] – 2026-03-25

### Hinzugefügt
- **Italienische Übersetzung** (it.json) – Config Flow, Sensornamen, Karten-UI
- **Entity-Übersetzungen** in allen 4 Sprachen – Sensornamen werden in der HA-Sprache angezeigt (Energiebezug, Consommation, Consumo, Energy import)
- **Lovelace-Karte mehrsprachig** – erkennt HA-Sprache automatisch (DE/EN/FR/IT)

### Geändert
- `strings.json` als Englisch-Fallback mit vollständigen Entity-Übersetzungen
- Alle Übersetzungen überarbeitet und vereinheitlicht (DE, EN, FR, IT)
- Lovelace-Karten-UI: Bezug/Einspeisung, Consommation/Injection, Consumo/Immissione

## [1.0.6] – 2026-03-25

### Geändert
- **Branding**: Alle Referenzen von „gPlug" auf korrekte Benennung umgestellt (Firma heisst gPlug, Produkte gPlugD/gPlugD-E/gPlugM/gPlugK)
- Betrifft README, CHANGELOG, Config Flow, Übersetzungen (DE/FR/EN), Lovelace-Karte, HACS-Metadaten

## [1.0.5] – 2026-03-25

### Behoben
- **Energy Dashboard Auto-Config komplett überarbeitet**: Verwendet jetzt das flache Grid-Format (ein Grid-Eintrag pro Tarif) statt `flow_from`/`flow_to` das bei vielen HA-Versionen Schema-Fehler verursachte
- Jeder Tarif wird als eigener Grid-Eintrag angelegt: HT (0.27 CHF/kWh), NT (0.21 CHF/kWh)
- Import und Export werden automatisch gepaart (HT↔HT, NT↔NT)
- Duplikat-Prüfung: Läuft nur einmal, überspringt wenn bereits ein gPlug-Sensor konfiguriert ist
- Bestehende Energy-Quellen (z.B. Aqara-Geräte) bleiben erhalten

## [1.0.4] – 2026-03-25

### Behoben
- **Keine Duplikate im Energy Dashboard**: Auto-Konfiguration prüft jetzt ob bereits gPlug-Sensoren im Energy Dashboard vorhanden sind und überspringt in diesem Fall
- Verhindert `duplicate unique ID` Fehler bei HA-Neustart wenn Sensoren bereits manuell oder durch vorherigen Lauf konfiguriert wurden

## [1.0.3] – 2026-03-25

### Behoben
- **Lovelace-Karte Cache-Busting**: Resource-URL enthält jetzt Versionsparameter (`?v=1.0.3`), damit Browser bei Updates die neue Version laden
- Bei Version-Update wird die bestehende Resource-URL automatisch aktualisiert (kein Duplikat)

## [1.0.2] – 2026-03-25

### Behoben
- **Lovelace-Karte wird jetzt zuverlässig registriert**: Schreibt direkt in `.storage/lovelace_resources` statt über die instabile interne Lovelace-API
- Karte erscheint nach HA-Neustart automatisch unter Einstellungen → Dashboards → Ressourcen
- Fallback mit manueller Anleitung falls Schreibzugriff fehlschlägt

## [1.0.1] – 2026-03-25

### Behoben
- **HA 2025.x+ Kompatibilität**: `async_register_static_paths` statt `register_static_path` (mit Fallback)
- **Manifest**: `http`, `lovelace`, `energy` in `after_dependencies`, korrekte Key-Sortierung
- **OptionsFlow**: Kompatibel mit neuerer HA `config_entry` Property
- **Device Registry**: Keine ungültige `configuration_url` bei reiner MQTT-Verbindung
- **Sensor-Erstellung**: `entity_id`-Check vor `async_write_ha_state()` verhindert `NoEntitySpecifiedError`
- **gPlugD Payload**: `z`-Prefix und Kurzkeys (`Pi`, `V1`, `Ei1` etc.) korrekt gemappt
- **SMid**: Meter-Seriennummer wird übersprungen (kein Sensor)

### Hinzugefügt
- Per-Phase Leistungssensoren: `P1i`/`P2i`/`P3i` und `P1o`/`P2o`/`P3o` (W)
- Offizielle gPlug Brand Assets (Logo, Icon)

## [1.0.0] – 2026-03-25

### Hinzugefügt
- **Auto-Discovery** aller Sensoren via MQTT (Prefixes: `z`, `ENERGY`, `SML`, `P1`, `HDLC`)
- **Energy Dashboard ready** – Sensoren mit `device_class: energy` / `state_class: total_increasing`
- **Auto-Konfiguration** des Energy Dashboards 30s nach HA-Start
- **Lovelace-Karte** (`gplug-energy-card`) mit Auto-Registrierung und visuellem Editor
- **Doppeltarif (HT/NT)** – optimiert für Schweizer VNB (z.B. EWZ Zürich)
- **3-Phasen-Monitoring** – Spannung, Strom, Leistung pro Phase (L1/L2/L3)
- **Config Flow** mit MQTT (empfohlen) und HTTP-Polling
- **Übersetzungen**: DE / FR / EN
- **Diagnostics** Support
- CI/CD: HACS + Hassfest + Ruff Validation
- Beispiel-Configs für `utility_meter`, Templates und Automations

### Kompatible Hardware
- gPlugD, gPlugD-E, gPlugE
- Smart Meter: Elster AS3000, Ensor eRS801, L&G E360, Sagemcom XT211, ISKRA AM550, NES Gen-5, M+C Flexy

[1.1.1]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.1.1
[1.1.0]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.1.0
[1.0.9]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.9
[1.0.8]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.8
[1.0.7]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.7
[1.0.6]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.6
[1.0.5]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.5
[1.0.4]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.4
[1.0.3]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.3
[1.0.2]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.2
[1.0.1]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.1
[1.0.0]: https://github.com/FX6W9WZK/ha-gPlug-energy/releases/tag/v1.0.0
