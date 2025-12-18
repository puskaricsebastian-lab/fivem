# HTL Upload – persönliche Cloud

Saubere Flask-Webapp zum Registrieren, Anmelden und Verwalten eigener Dateien/Ordner. Jeder Upload wird pro Benutzer unter `/opt/htl-upload/uploads/<username>/…` gespeichert und nur als relative Pfade im UI angezeigt.

## Features
- Login/Registrierung mit eindeutiger E-Mail und Username, Passwort-Regeln (min. 8 Zeichen, 1 Groß-, 1 Kleinbuchstabe, 1 Zahl), Passwort-Hashing.
- Dashboard mit Quick-Upload (Drag & Drop + Progress) und Liste der letzten Dateien.
- „Meine Dateien“ mit Suche, Sortierung (Name/Datum/Größe), Typ-/Datumsfilter, Favoriten, Mehrfachauswahl (Löschen, Download als ZIP, Verschieben, ZIP erstellen), Inline-Favoriten und Vorschau (Bilder/PDF inline, sonst Download).
- Ordner-Verwaltung: anlegen, umbenennen (wenn leer) und löschen (wenn leer), Breadcrumbs + Unterordner-Navigation.
- Shares: Dateien gezielt mit einem anderen Benutzer teilen, Freigaben verwalten, „Mit mir geteilt“ einsehen.
- Gruppen: Gruppen erstellen, Join-Code teilen, Beitritte genehmigen und gemeinsame Uploads für Mitglieder bereitstellen.
- Freunde & Chats: Freundschaftsanfragen senden/annehmen, Chat mit Text oder angehängten Dateien (Freigabe erfolgt automatisch beim Senden).
- Profil: Passwortwechsel direkt im UI.
- Uploads optional in einen ausgewählten Unterordner; nie absolute Pfade oder Traversal.
- Storage strikt pro Benutzer unter `/opt/htl-upload/uploads/<username>/…`; Dateidatenbank mit `files` (rel_path, filename, size, mime, favorite).

## Schnellstart (lokal)
1. **Voraussetzungen**: Python 3.10+, `pip`.
2. **Installieren**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\\Scripts\\Activate.ps1
   pip install -r requirements.txt
   ```
3. **.env anlegen (optional)**
   ```bash
   cp .env.example .env
   # Passe SECRET_KEY, DATABASE_URL (optional) und UPLOAD_ROOT an
   ```
4. **Starten**
   ```bash
   python app.py
   ```
   Die Seite läuft unter `http://localhost:5000`.
5. **Nutzung**
   - Auf `/` erscheint ein kompaktes Auth-Panel. Registrieren (E-Mail, Username, Passwort+Wiederholung) oder einloggen.
   - Dashboard: Quick Upload mit Drag & Drop und Fortschrittsbalken.
   - Dateien: Navigation über Breadcrumbs/Unterordner, Suche/Filter, Favoriten, Bulk-Aktionen, Vorschau/Download/Löschen, Ordner anlegen/umbenennen/löschen (nur leer), Bulk-Move mit Zielordner, gezielte Freigaben.
   - Shares/Gruppen: unter „Shares“ Freigaben anlegen/sehen, „Mit mir geteilt“ prüfen; unter „Gruppen“ Gruppen anlegen, Join-Code teilen/beitreten und Gruppen-Uploads nutzen.

## Deployment auf Ubuntu 22.04 (htl-upload.service)
1. **Code bereitstellen**: z. B. unter `/opt/htl-upload` ablegen.
2. **Python-Umgebung/Abhängigkeiten**
   ```bash
   cd /opt/htl-upload
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Env setzen** (`/opt/htl-upload/.env` oder systemd EnvironmentFile)
   ```bash
   SECRET_KEY=dein-geheimnis
   DATABASE_URL=sqlite:////opt/htl-upload/database.db   # oder PostgreSQL-URL
   UPLOAD_ROOT=/opt/htl-upload/uploads
   ```
4. **Systemd-Service (Beispiel)**
   ```ini
   [Service]
   WorkingDirectory=/opt/htl-upload
   EnvironmentFile=/opt/htl-upload/.env
   ExecStart=/opt/htl-upload/.venv/bin/python /opt/htl-upload/app.py
   Restart=always
   User=www-data
   ```
   Danach `systemctl daemon-reload && systemctl restart htl-upload` und Logs prüfen mit `journalctl -u htl-upload -n 100 --no-pager`.
5. **Reverse Proxy/HTTPS**: z. B. Nginx auf Port 80/443, Proxy auf `127.0.0.1:5000`, optional Let’s Encrypt.

## Datenbank
- Standard: SQLite (`database.db`) im Projektverzeichnis.
- Optional: `DATABASE_URL` (z. B. PostgreSQL). Tabellen `users`, `files`, `shares`, `groups`, `group_memberships`, `group_uploads` werden beim Start erstellt.

## Wichtige Pfade
- Upload-Root: `/opt/htl-upload/uploads/<username>/…` (konfigurierbar via `UPLOAD_ROOT`).
- UI zeigt nur relative Pfade ab Benutzer-Root, keine absoluten Serverpfade.

## Tests
- Syntax-Check: `python -m compileall .`
