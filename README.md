# HTL Upload

Elegante Weboberfläche zum Hochladen kompletter Ordner. Dateien werden lokal gespeichert und in einer SQLite-Datenbank protokolliert.

## Features
- Upload kompletter Ordner (inklusive Unterordner) per Browser (`webkitdirectory`).
- Speicherung auf dem lokalen Dateisystem unter `uploads/`.
- Protokoll in `database.db` mit Dateipfaden, Größen und Zeitstempeln.
- Moderner, dunkler Look mit Fokus auf Übersichtlichkeit.

## Voraussetzungen
- Python 3.10 oder neuer (prüfen mit `python --version` oder `python3 --version`).
- `pip` zum Installieren der Abhängigkeiten (unter macOS/Linux meist bereits dabei; unter Windows ggf. [Python-Installer](https://www.python.org/downloads/) neu ausführen und "Add python.exe to PATH" aktivieren).

## Schritt-für-Schritt-Anleitung
1. **Projektordner öffnen**  
   Beispiel: Wenn du das Repo ausgepackt hast, navigiere im Terminal oder in PowerShell nach `.../fivem`.

2. **(Optional) Virtuelle Umgebung anlegen**  
   So bleibt dein System sauber:
   ```bash
   python -m venv .venv
   # Umgebung aktivieren
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   # macOS/Linux (bash/zsh)
   source .venv/bin/activate
   ```

3. **Abhängigkeiten installieren**  
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Server starten**  
   ```bash
   python app.py
   ```
   Die Konsole zeigt dann `Running on http://127.0.0.1:5000`.

5. **Seite im Browser öffnen**  
   Rufe `http://localhost:5000` auf. Wähle im Formular einen Ordner (Chromium/Edge/Chrome unterstützen vollständige Ordner-Uploads) und klicke auf **Upload Folder**.

6. **Ergebnis prüfen**  
   Unterhalb des Formulars erscheint die Tabelle der letzten Uploads mit Datum, Pfad und Größe. Fehler oder Logs siehst du im Terminal.

> Hinweis: Das Hochladen kompletter Ordner wird aktuell vor allem von Chromium-basierten Browsern unterstützt. Safari/Firefox zeigen ggf. nur Dateiauswahl an.

## Wo liegt der Code und die Uploads?
- Der gesamte Quellcode liegt in diesem lokalen Projektordner (z. B. `/workspace/fivem` in der Entwicklungsumgebung).
- Hochgeladene Dateien landen auf derselben Maschine im Unterordner `uploads/`; die Metadaten speichert die App in `database.db`.
- Standardmäßig wird nichts automatisch nach GitHub übertragen. Wenn du das Projekt in ein eigenes GitHub-Repository pushen möchtest, kannst du dort ein neues Repo anlegen und die vorhandenen Dateien hochladen.
