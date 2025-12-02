from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from flask import (  # noqa: E402
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from openpyxl import load_workbook  # noqa: E402
from werkzeug.datastructures import FileStorage  # noqa: E402

from models import (  # noqa: E402
    add_person_rows,
    add_upload,
    fetch_recent_uploads,
    fetch_upload,
    fetch_uploads_desc,
    get_session,
    init_db,
)

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB limit
ALLOWED_EXCEL_SUFFIXES = {".xlsx"}


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


def ensure_upload_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def build_storage_paths(folder_label: str, relative: Path) -> tuple[Path, Path]:
    today = datetime.utcnow()
    relative_server = Path("uploads") / f"{today:%Y}" / f"{today:%m}" / folder_label / relative
    destination = BASE_DIR / relative_server
    return destination, relative_server


def save_file(session, file_storage: FileStorage, folder_label: str, uploader_ip: str | None):
    relative = sanitize_relative_path(file_storage.filename)
    if not relative.parts:
        return None

    destination, server_relative = build_storage_paths(folder_label, relative)
    ensure_upload_dir(destination)
    file_storage.save(destination)

    size = destination.stat().st_size
    content_type = file_storage.mimetype or "application/octet-stream"
    upload = add_upload(
        session,
        original_filename=str(relative),
        server_path=str(server_relative),
        size_bytes=size,
        content_type=content_type,
        uploader_ip=uploader_ip,
    )
    return upload


def parse_excel_names(file_storage):
    suffix = Path(file_storage.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXCEL_SUFFIXES:
        raise ValueError("Ungültiger Dateityp. Bitte eine .xlsx-Datei hochladen.")

    file_storage.stream.seek(0)
    try:
        workbook = load_workbook(file_storage, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Die Datei konnte nicht gelesen werden. Bitte das offizielle Template verwenden.") from exc

    sheet = workbook.active
    header_rows = sheet.iter_rows(max_row=1, values_only=False)
    try:
        first_row = next(header_rows)
    except StopIteration as exc:  # empty sheet
        raise ValueError("Leere Datei. Bitte das offizielle Template verwenden.") from exc

    header = [str(cell.value).strip().lower() if cell.value is not None else "" for cell in first_row]
    if len(header) < 2 or header[0] != "vorname" or header[1] != "nachname":
        raise ValueError("Ungültiges Format – bitte das offizielle Template verwenden.")

    names = []
    for first_name, last_name in sheet.iter_rows(min_row=2, max_col=2, values_only=True):
        if first_name is None and last_name is None:
            continue
        first_clean = str(first_name).strip() if first_name is not None else ""
        last_clean = str(last_name).strip() if last_name is not None else ""
        if not first_clean and not last_clean:
            continue
        names.append({"vorname": first_clean, "nachname": last_clean})

    if not names:
        raise ValueError("Keine Namen gefunden. Bitte Zeilen ausfüllen und erneut versuchen.")

    return names


def render_home(*, names=None, success_message=None, error_message=None):
    session = get_session()
    try:
        uploads = fetch_recent_uploads(session)
    finally:
        session.close()
    return render_template(
        "index.html",
        uploads=uploads,
        names=names or [],
        success_message=success_message,
        error_message=error_message,
    )


@app.route("/")
def index():
    success_message = None
    if request.args.get("success") == "true":
        success_message = "Upload erfolgreich gespeichert – Einträge sind nun von überall abrufbar."

    return render_home(success_message=success_message)


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    folder_label_input = request.form.get("folderName", "")
    folder_label = sanitize_folder_label(folder_label_input)

    if not files:
        return jsonify({"error": "Keine Dateien erhalten."}), 400

    session = get_session()
    saved = 0
    try:
        for file_storage in files:
            uploaded = save_file(session, file_storage, folder_label, request.remote_addr)
            if uploaded:
                saved += 1
        if saved == 0:
            session.rollback()
            return jsonify({"error": "Es konnte nichts gespeichert werden."}), 400
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        return jsonify({"error": "Speichern fehlgeschlagen."}), 500
    finally:
        session.close()

    return redirect(url_for("index", success="true"))


@app.route("/upload-namensliste", methods=["GET", "POST"])
def upload_namensliste():
    if request.method == "GET":
        return render_home()

    file_storage = request.files.get("namensliste")
    if not file_storage or file_storage.filename == "":
        return render_home(error_message="Bitte wähle eine Excel-Datei aus.")

    try:
        names = parse_excel_names(file_storage)
    except ValueError as exc:
        return render_home(error_message=str(exc))
    except Exception:  # noqa: BLE001
        return render_home(
            error_message="Die Namensliste konnte nicht verarbeitet werden. Bitte das offizielle Template verwenden."
        )

    session = get_session()
    folder_label = sanitize_folder_label(Path(file_storage.filename).stem)
    try:
        file_storage.stream.seek(0)
        uploaded = save_file(session, file_storage, folder_label, request.remote_addr)
        if not uploaded:
            session.rollback()
            return render_home(error_message="Es konnte nichts gespeichert werden.")
        add_person_rows(session, uploaded, names)
        session.commit()
    except Exception:  # noqa: BLE001
        session.rollback()
        return render_home(error_message="Die Namensliste konnte nicht gespeichert werden.")
    finally:
        session.close()

    return render_home(
        names=names,
        success_message="Upload erfolgreich gespeichert – Einträge sind nun von überall abrufbar.",
    )


@app.route("/admin/uploads")
def admin_uploads():
    session = get_session()
    try:
        uploads = fetch_uploads_desc(session)
    finally:
        session.close()
    return render_template("admin_uploads.html", uploads=uploads)


@app.route("/admin/uploads/<int:upload_id>")
def admin_upload_detail(upload_id: int):
    session = get_session()
    try:
        upload_obj = fetch_upload(session, upload_id)
        if not upload_obj:
            abort(404)
    finally:
        session.close()
    return render_template("admin_upload_detail.html", upload=upload_obj)


@app.route("/download/<int:upload_id>")
def download(upload_id: int):
    session = get_session()
    try:
        upload_obj = fetch_upload(session, upload_id)
    finally:
        session.close()

    if not upload_obj:
        abort(404)

    file_path = BASE_DIR / upload_obj.server_path
    if not file_path.exists():
        abort(404)

    return send_file(file_path, as_attachment=True, download_name=Path(upload_obj.original_filename).name)


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
