# HTL Upload

Elegante Weboberfläche zum Hochladen kompletter Ordner. Fürs Ausprobieren läuft alles direkt lokal mit einer integrierten SQLite-Datei; eine zentrale Online-Datenbank (z. B. PostgreSQL) kannst du später per `DATABASE_URL` anbinden.

## Features
- Login-Pflicht mit Benutzerkonten (E-Mail + Username + Passwort, gehasht gespeichert) und Plänen Free/Premium/Trial; E-Mail und Username sind eindeutig.
- Upload kompletter Ordner (inklusive Unterordner) per Browser (`webkitdirectory`) – jedem Upload wird der aktuelle Benutzer zugeordnet; Drag & Drop mit Fortschrittsbalken ist aktiv.
- Persönliche Cloud-Ansicht unter „Meine Dateien“: alle eigenen Uploads mit Download- und Lösch-Buttons (löscht auch die physische Datei) plus Sortierung nach Name/Datum/Größe.
- Speicherung auf dem Server-Dateisystem pro Benutzer unter `uploads/<user_id>/<jahr>/<monat>/...`; Metadaten in SQLite (lokal) oder optional in einer zentralen DB via `DATABASE_URL` (z. B. PostgreSQL).
- Upload einer Excel-Namensliste (.xlsx) mit Vor-/Nachname; alle Namen landen in der Tabelle `persons` und gehören zum jeweiligen Nutzer.
- Shares: Besitzer können eigene Uploads gezielt mit anderen Usern per Benutzername teilen („Mit mir geteilt“ / „Meine Shares“ inkl. Entzug des Zugriffs).
- Gruppen: Join-Code-basierte Gruppen mit Admin-Freigabe von Beitrittsanfragen, Gruppen-Uploads (für alle akzeptierten Mitglieder sichtbar) und Gruppen-Detailseite.
- Admin-Bereich (`/admin/login`, `/admin/uploads`, `/admin`) für vollständige Historie aller Nutzer (nur `is_admin=True`).
- Konfigurierbare Upload- und Speicherlimits: `MAX_UPLOAD_MB` (pro Anfrage), `MAX_FILE_SIZE_MB` (pro Datei) und optional `MAX_STORAGE_PER_USER_MB` (Gesamtspeicher pro Nutzer).

### Benutzer & Quoten
- Free: 5 Uploads pro Tag und Benutzer.
- Trial/Premium: unbegrenzt. Trial kann über die Einstellungen gestartet werden.
- Alle Passwörter werden gehasht gespeichert (`werkzeug.security`), Sessions laufen über Flask mit `SECRET_KEY`.
- Downloads/Löschungen sind nur im eingeloggten Zustand möglich; pro Datei wird geprüft, ob sie dem aktuellen Nutzer gehört (oder ob `is_admin=True`). Zugriff ist außerdem möglich, wenn ein Share für dich existiert oder du Mitglied der Gruppe eines Gruppen-Uploads bist.

## Voraussetzungen
- Python 3.10 oder neuer (prüfen mit `python --version` oder `python3 --version`).
- `pip` zum Installieren der Abhängigkeiten (unter macOS/Linux meist bereits dabei; unter Windows ggf. [Python-Installer](https://www.python.org/downloads/) neu ausführen und "Add python.exe to PATH" aktivieren).
- Ein `SECRET_KEY` für Flask-Sessions (z. B. in `.env` setzen: `SECRET_KEY=irgendein_geheimnis`).

## Schritt-für-Schritt mit PhpStorm (von 0 auf)
1. **Projekt in PhpStorm öffnen**
   - `File > Open…` und den Ordner `fivem` auswählen.
   - PhpStorm erkennt eine Python-App; falls gefragt, „This window“ bestätigen.

2. **Interpreter + (optional) virtuelle Umgebung**
   - Unten rechts auf die Python-Version klicken → „Add New Interpreter…“ → „Virtualenv Environment“ → „OK“. PhpStorm legt `.venv` an und nutzt sie automatisch.
   - Alternativ kannst du im integrierten Terminal manuell anlegen:
     ```bash
     python -m venv .venv
     # Windows (PowerShell)
     .venv\Scripts\Activate.ps1
     # macOS/Linux (bash/zsh)
     source .venv/bin/activate
     ```

3. **Abhängigkeiten installieren**
   - Im PhpStorm-Terminal (unten):
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```
   - PhpStorm zeigt gefundene Packages auch in `Python Packages`; falls etwas fehlt, kannst du dort nachinstallieren.

4. **(Optional) Umgebungsvariablen setzen**
   - Für den Schnellstart ist nichts nötig (es wird automatisch `database.db` als lokale SQLite genutzt).
   - Wenn du zentral testen willst: In PhpStorm `Run > Edit Configurations…` → `+` → „Python“ → Script `app.py` wählen → unter „Environment variables“ `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/htl_upload` eintragen. Hier kannst du auch `SECRET_KEY=etwas-langes-und-geheimes` setzen.
   - Tabellen (`users`, `uploads`, `persons`) werden beim Start automatisch erstellt.
   - Upload-Limits kannst du anpassen mit `MAX_UPLOAD_MB` (pro Anfrage, Default 500), `MAX_FILE_SIZE_MB` (pro Datei, Default = `MAX_UPLOAD_MB`) und `MAX_STORAGE_PER_USER_MB` (optionaler Gesamtspeicher pro Nutzer in MB).

5. **Run/Debug-Konfiguration anlegen**
   - `Run > Edit Configurations…` → `+` → „Python“ → Name z. B. „HTL Upload“ → Script path: `app.py` → Interpreter: deine `.venv` → OK.
   - Alternativ über das Play-Symbol oben rechts einen neuen „Python“-Run anlegen.

6. **Server starten**
   - Mit dem Play-Button („Run HTL Upload“) oder Debug-Button in PhpStorm starten.
   - Im „Run“-Toolfenster siehst du die Ausgabe `Running on http://127.0.0.1:5000`.

7. **Seite im Browser öffnen und testen**
   - `http://localhost:5000` aufrufen. Die Landing erklärt den Funktionsumfang; Login/Registrierung erfolgt direkt dort.
   - **Registrieren/Anmelden:** E-Mail + Username + Passwort ausfüllen (Passwort-Wiederholung nötig). Plan wählen (Free = 5 Uploads/Tag, Premium/Trial = unbegrenzt). Nach Login wirst du in den Workspace geleitet; die Session ist „remembered“.
   - **Uploads:** Im Workspace (`/app`) Ordner oder Excel-Namensliste hochladen. Jede Datei wird deinem Benutzerkonto zugeordnet. Drag & Drop und Fortschrittsanzeige sind aktiv. Falls ein Limit verletzt wird (Datei > `MAX_FILE_SIZE_MB`, Anfrage > `MAX_UPLOAD_MB` oder Gesamt > `MAX_STORAGE_PER_USER_MB`), erscheint eine freundliche Fehlermeldung.
   - **Meine Dateien:** Unter `/my/uploads` siehst du alle eigenen Uploads, kannst sortieren (Name/Datum/Größe), herunterladen oder löschen (löscht auch die Datei auf dem Server). Speicherverbrauch wird angezeigt.
   - **Shares & Gruppen:**
     - Unter `/shares/new` einen eigenen Upload mit einem anderen User (per Username) teilen, Übersicht unter `/shares/mine` bzw. „Mit mir geteilt“.
     - Gruppen findest du unter `/groups`: neue Gruppen anlegen (Join-Code wird generiert), per Join-Code beitreten, Anfragen als Gruppen-Admin bestätigen/ablehnen und Gruppen-Uploads hochladen/herunterladen.
   - **Historie & Downloads (Admin):** `http://localhost:5000/admin/uploads` zeigt alle Uploads aller Nutzer, nur erreichbar mit `is_admin=True`.

> Hinweis: Ordner-Upload funktioniert primär in Chromium-basierten Browsern. Safari/Firefox zeigen ggf. nur Dateiauswahl.

## Wo liegt der Code und die Uploads?
- Der gesamte Quellcode liegt in diesem Projektordner (z. B. `/workspace/fivem` in der Entwicklungsumgebung oder im Deploy-Verzeichnis auf dem Server).
- Hochgeladene Dateien landen auf dem Server im Unterordner `uploads/<user_id>/<jahr>/<monat>/...`; die Metadaten schreibt die App standardmäßig in die lokale SQLite-Datei `database.db` (per `DATABASE_URL` später auf eine zentrale DB umstellbar). Shares und Gruppen referenzieren dieselben Uploads.
- Standardmäßig wird nichts automatisch nach GitHub übertragen. Wenn du das Projekt in ein eigenes GitHub-Repository pushen möchtest, kannst du dort ein neues Repo anlegen und die vorhandenen Dateien hochladen.

> Hinweis: Ich kann den Server/die Datenbank aus Sicherheitsgründen nicht selbst für dich aufsetzen oder Zugangsdaten entgegennehmen. Die obigen Schritte kannst du direkt auf deinem Root-Server ausführen (z. B. mit systemd + Nginx/Gunicorn für einen dauerhaften Betrieb).
