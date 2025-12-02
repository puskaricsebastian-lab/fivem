import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "database.db"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB limit


def init_storage():
    UPLOAD_DIR.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folder_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def sanitize_relative_path(path: str) -> Path:
    cleaned_parts = []
    for part in Path(path).parts:
        if part in {"..", ".", ""}:
            continue
        cleaned_parts.append(part)
    return Path(*cleaned_parts)


def sanitize_folder_label(label: str) -> str:
    cleaned = "".join(ch for ch in label if ch.isalnum() or ch in {" ", "_", "-"}).strip()
    return cleaned or "Ordner"


def save_file(file_storage, folder_label: str):
    relative = sanitize_relative_path(file_storage.filename)
    if not relative.parts:
        return None

    destination = UPLOAD_DIR / folder_label / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)

    size = destination.stat().st_size
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO uploads (folder_name, relative_path, stored_path, size_bytes, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                folder_label,
                str(relative),
                str(destination.relative_to(BASE_DIR)),
                size,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return relative


@app.route("/")
def index():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT folder_name, relative_path, stored_path, size_bytes, uploaded_at
            FROM uploads
            ORDER BY uploaded_at DESC
            LIMIT 25
            """
        ).fetchall()
    return render_template("index.html", uploads=rows)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    folder_label_input = request.form.get("folderName", "")
    folder_label = sanitize_folder_label(folder_label_input)

    if not files:
        return jsonify({"error": "Keine Dateien erhalten."}), 400

    saved = 0
    for file_storage in files:
        saved_path = save_file(file_storage, folder_label)
        if saved_path:
            saved += 1

    if saved == 0:
        return jsonify({"error": "Es konnte nichts gespeichert werden."}), 400

    return redirect(url_for("index"))


init_storage()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
