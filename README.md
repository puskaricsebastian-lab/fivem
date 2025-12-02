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

## Wo liegt der Code und die Uploads?
- Der gesamte Quellcode liegt in diesem lokalen Projektordner (z. B. `/workspace/fivem` in der Entwicklungsumgebung).
- Hochgeladene Dateien landen auf derselben Maschine im Unterordner `uploads/`; die Metadaten speichert die App in `database.db`.
- Standardmäßig wird nichts automatisch nach GitHub übertragen. Wenn du das Projekt in ein eigenes GitHub-Repository pushen möchtest, kannst du dort ein neues Repo anlegen und die vorhandenen Dateien hochladen.
