# HTL Upload

Elegante Weboberfläche zum Hochladen kompletter Ordner. Dateien werden lokal gespeichert und in einer SQLite-Datenbank protokolliert.

## Features
- Upload kompletter Ordner (inklusive Unterordner) per Browser (`webkitdirectory`).
- Speicherung auf dem lokalen Dateisystem unter `uploads/`.
- Protokoll in `database.db` mit Dateipfaden, Größen und Zeitstempeln.
- Moderner, dunkler Look mit Fokus auf Übersichtlichkeit.

## Schnellstart
1. Abhängigkeiten installieren:
   ```bash
   pip install -r requirements.txt
   ```
2. Server starten:
   ```bash
   python app.py
   ```
3. Die Seite unter `http://localhost:5000` öffnen und den gewünschten Ordner hochladen.

> Hinweis: Das Hochladen kompletter Ordner wird aktuell vor allem von Chromium-basierten Browsern unterstützt.
