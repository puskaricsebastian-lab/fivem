# HTL Upload

Elegante Weboberfläche zum Hochladen kompletter Ordner. Dateien werden zentral gespeichert, in einer Online-Datenbank (z. B. PostgreSQL) protokolliert und sind nur nach Login verfügbar.

## Features
- Upload kompletter Ordner (inklusive Unterordner) per Browser (`webkitdirectory`).
- Speicherung auf dem Server-Dateisystem unter `uploads/<jahr>/<monat>/...`.
- Protokoll in einer zentral erreichbaren Datenbank (PostgreSQL empfohlen) inklusive Download-Links.
- Moderner, dunkler Look mit Fokus auf Übersichtlichkeit.
- Upload einer Excel-Namensliste (.xlsx) mit Anzeige aller Vor- und Nachnamen auf der Seite; alle Namen werden in der Tabelle `persons` gespeichert.
- Login-Pflicht mit Registrierung (E-Mail + Passwort), Tarifwahl (Free/Premium) und täglichem Freikontingent für Free (5 Uploads pro Tag, pro Datei gezählt).
- Admin-Bereich (`/admin/uploads`) mit Historie, Details und Download-Links, damit auch andere Geräte auf die Dateien zugreifen können.

## Voraussetzungen
- Python 3.10 oder neuer (prüfen mit `python --version` oder `python3 --version`).
- `pip` zum Installieren der Abhängigkeiten (unter macOS/Linux meist bereits dabei; unter Windows ggf. [Python-Installer](https://www.python.org/downloads/) neu ausführen und "Add python.exe to PATH" aktivieren).
- Eine erreichbare Datenbank (PostgreSQL oder kompatibel) und eine gültige `DATABASE_URL` (z. B. `postgresql+psycopg2://user:pass@host:5432/htl_upload`).
- Ein `SECRET_KEY` für Flask-Sessions (z. B. in `.env` setzen: `SECRET_KEY=irgendein_geheimnis`).

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

4. **Datenbank konfigurieren**
   Setze `DATABASE_URL` (z. B. in einer `.env`-Datei oder direkt als Umgebungsvariable), damit die App die zentrale Datenbank erreicht:
   ```bash
   export DATABASE_URL="postgresql+psycopg2://user:pass@host:5432/htl_upload"
   ```
   Optional legst du auch `SECRET_KEY` hier ab:
   ```bash
   export SECRET_KEY="etwas-langes-und-geheimes"
   ```
   Die Tabellen `users`, `uploads` (für alle Dateien) und `persons` (für Excel-Namen) werden beim Start automatisch erstellt.

5. **Server starten**
   ```bash
   python app.py
   ```
   Die Konsole zeigt dann `Running on http://127.0.0.1:5000`. Wird der Server auf einem Hoster mit fester URL betrieben, sind Uploads und Downloads von überall erreichbar.

6. **Seite im Browser öffnen**
   Rufe `http://localhost:5000` auf.

   - **Registrieren**: E-Mail, Passwort und Tarif auswählen (Free = 5 Uploads pro Tag, Premium = unbegrenzt). Nach erfolgreicher Registrierung oder Anmeldung erscheint oben ein grüner Hinweis.
   - **Upload**: Wähle einen Ordner oder eine Excel-Namensliste. Uploads werden nur gespeichert, wenn du eingeloggt bist und (im Free-Tarif) das Tageslimit nicht überschreitest.

7. **Ergebnis prüfen**
   Unterhalb des Formulars erscheint die Tabelle der letzten Uploads mit Datum, Pfad und Größe. Im Admin-Bereich `http://localhost:5000/admin/uploads` kannst du alle Uploads samt Download-Link einsehen – auch remote erreichbar, wenn der Server öffentlich läuft. Fehler oder Logs siehst du im Terminal.

> Hinweis: Das Hochladen kompletter Ordner wird aktuell vor allem von Chromium-basierten Browsern unterstützt. Safari/Firefox zeigen ggf. nur Dateiauswahl an.

## Wo liegt der Code und die Uploads?
- Der gesamte Quellcode liegt in diesem Projektordner (z. B. `/workspace/fivem` in der Entwicklungsumgebung oder im Deploy-Verzeichnis auf dem Server).
- Hochgeladene Dateien landen auf dem Server im Unterordner `uploads/<jahr>/<monat>/...`; die Metadaten schreibt die App in die konfigurierte zentrale Datenbank (`DATABASE_URL`).
- Standardmäßig wird nichts automatisch nach GitHub übertragen. Wenn du das Projekt in ein eigenes GitHub-Repository pushen möchtest, kannst du dort ein neues Repo anlegen und die vorhandenen Dateien hochladen.

> Hinweis: Ich kann den Server/die Datenbank aus Sicherheitsgründen nicht selbst für dich aufsetzen oder Zugangsdaten entgegennehmen. Die obigen Schritte kannst du direkt auf deinem Root-Server ausführen (z. B. mit systemd + Nginx/Gunicorn für einen dauerhaften Betrieb).
