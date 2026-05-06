# Breeez Terminal Suite

Lokale Terminal-Web-App (Hacker-Style) mit verschlüsseltem Passwort-Manager.

## 1) Direkt im Browser starten

Einfach `index.html` doppelklicken oder im Browser öffnen.

## 2) In eine `.exe` umwandeln (Windows)

> Voraussetzung: Windows-System (oder Windows CI), Node.js 18+ installiert.

### Schritt-für-Schritt

1. Abhängigkeiten installieren:
   ```bash
   npm install
   ```

2. App lokal als Desktop-Fenster testen:
   ```bash
   npm run start
   ```

3. Portable `.exe` bauen:
   ```bash
   npm run dist:win
   ```

4. Ergebnis findest du dann hier:
   - `dist/Breeez Terminal Suite 1.0.0.exe` (portable)

## Hinweise

- Alles bleibt lokal auf dem Gerät.
- Keine Cloud, keine externen APIs, kein Tracking.
- Der Passwort-Manager speichert verschlüsselt im lokalen Speicher der App.
- Master-Passwort ist: `Breeez`.

## Optional: Angefügtes Bild einbinden

Wenn du dein Bild wie im Mockup nutzen willst, lege die Datei als

- `fsociety.png`

in denselben Ordner wie `index.html`.
