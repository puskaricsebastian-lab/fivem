# HTL Upload

Elegante Weboberfläche zum Hochladen kompletter Ordner. Fürs Ausprobieren läuft alles direkt lokal mit einer integrierten SQLite-Datei; eine zentrale Online-Datenbank (z. B. PostgreSQL) kannst du später per `DATABASE_URL` anbinden.

## Features
- Upload kompletter Ordner (inklusive Unterordner) per Browser (`webkitdirectory`).
- Speicherung auf dem Server-Dateisystem unter `uploads/<jahr>/<monat>/...`.
- Protokoll in einer Datenbank: Out of the box SQLite (lokale `database.db`), optional zentral erreichbar via `DATABASE_URL` (z. B. PostgreSQL) inklusive Download-Links.
- Moderner, dunkler Look mit Fokus auf Übersichtlichkeit.
- Upload einer Excel-Namensliste (.xlsx) mit Anzeige aller Vor- und Nachnamen auf der Seite; alle Namen werden in der Tabelle `persons` gespeichert.
- Gast-Demo ohne Anmeldung (2 Uploads pro Tag), wahlweise Registrierung mit Tarifen Free/Premium und Premium-Trial (Free: 5 Uploads/Tag, Premium/Trial: unbegrenzt).
- Admin-Bereich (`/admin/uploads`) mit Historie, Details und Download-Links; geschütztes Admin-Panel unter `/admin`.

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

5. **Run/Debug-Konfiguration anlegen**
   - `Run > Edit Configurations…` → `+` → „Python“ → Name z. B. „HTL Upload“ → Script path: `app.py` → Interpreter: deine `.venv` → OK.
   - Alternativ über das Play-Symbol oben rechts einen neuen „Python“-Run anlegen.

6. **Server starten**
   - Mit dem Play-Button („Run HTL Upload“) oder Debug-Button in PhpStorm starten.
   - Im „Run“-Toolfenster siehst du die Ausgabe `Running on http://127.0.0.1:5000`.

7. **Seite im Browser öffnen und testen**
   - `http://localhost:5000` aufrufen. Zuerst erscheint die Landing mit kurzer Erklärung.
   - **Gast-Demo:** Auf „Gast-Demo starten“ klicken (2 Uploads/Tag), ohne Login testen.
   - **Registrieren/Anmelden:** E-Mail + Passwort eingeben, Tarif wählen (Free = 5 Uploads pro Tag, Premium = unbegrenzt, Trial = 7 Tage). Nach Login erscheint eine Erfolgsmeldung.
   - **Uploads:** Ordner oder Excel-Namensliste auswählen und hochladen – Gast- und angemeldete Nutzer werden akzeptiert.
   - **Historie & Downloads:** `http://localhost:5000/admin/uploads` (Admin-Login erforderlich) zeigt alle Uploads mit Download-Link. Fehler/Logs stehen im PhpStorm-Run-Fenster.

> Hinweis: Ordner-Upload funktioniert primär in Chromium-basierten Browsern. Safari/Firefox zeigen ggf. nur Dateiauswahl.

## Wo liegt der Code und die Uploads?
- Der gesamte Quellcode liegt in diesem Projektordner (z. B. `/workspace/fivem` in der Entwicklungsumgebung oder im Deploy-Verzeichnis auf dem Server).
- Hochgeladene Dateien landen auf dem Server im Unterordner `uploads/<jahr>/<monat>/...`; die Metadaten schreibt die App standardmäßig in die lokale SQLite-Datei `database.db` (per `DATABASE_URL` später auf eine zentrale DB umstellbar).
- Standardmäßig wird nichts automatisch nach GitHub übertragen. Wenn du das Projekt in ein eigenes GitHub-Repository pushen möchtest, kannst du dort ein neues Repo anlegen und die vorhandenen Dateien hochladen.

> Hinweis: Ich kann den Server/die Datenbank aus Sicherheitsgründen nicht selbst für dich aufsetzen oder Zugangsdaten entgegennehmen. Die obigen Schritte kannst du direkt auf deinem Root-Server ausführen (z. B. mit systemd + Nginx/Gunicorn für einen dauerhaften Betrieb).
