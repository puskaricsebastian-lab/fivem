import os
from datetime import date, datetime, timedelta
from pathlib import Path
import secrets

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
    session as flask_session,
    url_for,
)
from openpyxl import load_workbook  # noqa: E402
from werkzeug.datastructures import FileStorage  # noqa: E402
from werkzeug.security import check_password_hash, generate_password_hash  # noqa: E402

from models import (  # noqa: E402
    User,
    add_person_rows,
    add_upload,
    count_uploads_for_date,
    create_user,
    fetch_upload,
    fetch_user_uploads,
    fetch_uploads_desc,
    get_session,
    get_user_by_email,
    get_user_by_id,
    init_db,
    reset_daily_counter_if_needed,
)

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 512 * 1024 * 1024  # 512 MB limit
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
ALLOWED_EXCEL_SUFFIXES = {".xlsx"}
FREE_DAILY_LIMIT = 5


def is_trial_active(user: User) -> bool:
    if not user or not user.trial_expires_at:
        return False
    if user.trial_expires_at >= datetime.utcnow():
        return True
    user.plan = "free"
    return False


def get_current_user(db_session) -> User | None:
    user_id = flask_session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(db_session, user_id)


def get_theme(user: User | None) -> str:
    if user and user.theme:
        flask_session["theme"] = user.theme
        return user.theme
    return flask_session.get("theme", "dark")


def require_user(db_session):
    user = get_current_user(db_session)
    if not user:
        return None
    ensure_csrf_token()
    return user


def set_theme_preference(user: User | None, theme: str) -> None:
    normalized = "light" if theme == "light" else "dark"
    flask_session["theme"] = normalized
    if user:
        user.theme = normalized


def ensure_csrf_token() -> str:
    token = flask_session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        flask_session["csrf_token"] = token
    return token


def enforce_quota(db_session, user: User, pending_uploads: int) -> tuple[bool, int]:
    """Return (allowed, remaining) for today."""

    reset_daily_counter_if_needed(user)
    today_count = count_uploads_for_date(db_session, user.id, date.today())
    if user.plan == "premium" or is_trial_active(user):
        return True, -1

    remaining = FREE_DAILY_LIMIT - today_count
    if pending_uploads > remaining:
        return False, remaining

    return True, remaining - pending_uploads


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


def save_file(
    session,
    file_storage: FileStorage,
    folder_label: str,
    uploader_ip: str | None,
    *,
    user_id: int,
):
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
        user_id=user_id,
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


def render_workspace(db_session, user: User, *, names=None, success_message=None, error_message=None):
    uploads = fetch_user_uploads(db_session, user.id, limit=25)
    today_count = count_uploads_for_date(db_session, user.id, date.today())
    theme = get_theme(user)
    ensure_csrf_token()
    return render_template(
        "index.html",
        uploads=uploads,
        names=names or [],
        success_message=success_message,
        error_message=error_message,
        user=user,
        daily_limit=FREE_DAILY_LIMIT,
        today_count=today_count,
        theme=theme,
        datetime=datetime,
        csrf_token=flask_session.get("csrf_token"),
    )


def success_text_from_query(param: str | None) -> str | None:
    mapping = {
        "registered": "Registrierung erfolgreich – du bist jetzt eingeloggt.",
        "logged_in": "Login erfolgreich.",
        "upload_saved": "Upload erfolgreich gespeichert – deine Dateien sind in deiner Cloud sichtbar.",
        "namensliste_saved": "Namensliste gespeichert und verknüpft.",
        "deleted": "Datei wurde aus deiner Cloud gelöscht.",
        "logged_out": "Abgemeldet.",
    }
    return mapping.get(param or "")


def error_text_from_query(param: str | None) -> str | None:
    mapping = {
        "login_required": "Bitte zuerst einloggen, um fortzufahren.",
        "unauthorized": "Kein Zugriff auf diese Datei.",
    }
    return mapping.get(param or "")


def render_landing_page(*, success_message=None, error_message=None):
    theme = get_theme(None)
    return render_template(
        "landing.html",
        theme=theme,
        success_message=success_message,
        error_message=error_message,
        daily_limit=FREE_DAILY_LIMIT,
    )


@app.route("/")
def landing():
    db_session = get_session()
    try:
        user = get_current_user(db_session)
        if user:
            return redirect(url_for("app_home"))
    finally:
        db_session.close()

    success_message = success_text_from_query(request.args.get("success"))
    error_message = error_text_from_query(request.args.get("error")) or request.args.get("message")
    return render_landing_page(success_message=success_message, error_message=error_message)


@app.route("/app")
def app_home():
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        success_message = success_text_from_query(request.args.get("success"))
        error_message = error_text_from_query(request.args.get("error")) or request.args.get("message")
        return render_workspace(
            db_session,
            user,
            success_message=success_message,
            error_message=error_message,
        )
    finally:
        db_session.close()


@app.route("/register", methods=["POST"])
def register():
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    confirm = request.form.get("password_confirm") or ""
    plan = (request.form.get("plan") or "free").strip().lower()
    if plan not in {"free", "premium"}:
        plan = "free"

    if not email or not password:
        return render_landing_page(error_message="Bitte E-Mail und Passwort ausfüllen.")
    if password != confirm:
        return render_landing_page(error_message="Passwörter stimmen nicht überein.")

    db_session = get_session()
    try:
        if get_user_by_email(db_session, email):
            return render_landing_page(error_message="Diese E-Mail ist bereits registriert.")

        password_hash = generate_password_hash(password)
        user = create_user(db_session, email=email, password_hash=password_hash, plan=plan)
        db_session.commit()
        flask_session["user_id"] = user.id
    except Exception:  # noqa: BLE001
        db_session.rollback()
        return render_landing_page(error_message="Registrierung fehlgeschlagen. Bitte später erneut versuchen.")
    finally:
        db_session.close()

    return redirect(url_for("app_home", success="registered"))


@app.route("/login", methods=["POST"])
def login():
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""

    if not email or not password:
        return render_landing_page(error_message="Bitte E-Mail und Passwort ausfüllen.")

    db_session = get_session()
    try:
        user = get_user_by_email(db_session, email)
        if not user or not check_password_hash(user.password_hash, password):
            return render_landing_page(error_message="Login fehlgeschlagen. Bitte E-Mail und Passwort prüfen.")
        flask_session["user_id"] = user.id
    finally:
        db_session.close()

    return redirect(url_for("app_home", success="logged_in"))


@app.route("/logout", methods=["POST"])
def logout():
    flask_session.pop("user_id", None)
    return redirect(url_for("landing", success="logged_out"))


@app.route("/settings", methods=["GET", "POST"])
def settings():
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))
        theme = get_theme(user)

        if request.method == "POST":
            action = request.form.get("action")
            if action == "theme":
                set_theme_preference(user, request.form.get("theme", "dark"))
                if user:
                    db_session.commit()
                return render_template(
                    "settings.html",
                    user=user,
                    theme=get_theme(user),
                    message="Theme aktualisiert.",
                    datetime=datetime,
                )

            if action == "start_trial" and user:
                if is_trial_active(user):
                    message = "Trial läuft bereits."
                else:
                    user.plan = "trial"
                    user.trial_expires_at = datetime.utcnow() + timedelta(days=7)
                    db_session.commit()
                    message = "7-Tage-Premium-Trial gestartet."
                return render_template(
                    "settings.html",
                    user=user,
                    theme=get_theme(user),
                    message=message,
                    datetime=datetime,
                )

        return render_template("settings.html", user=user, theme=theme, datetime=datetime)
    finally:
        db_session.close()


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    folder_label_input = request.form.get("folderName", "")
    folder_label = sanitize_folder_label(folder_label_input)

    if not files:
        return redirect(url_for("app_home", message="Keine Dateien erhalten."))

    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        allowed, remaining = enforce_quota(db_session, user, len(files))
        if not allowed:
            msg = (
                "Freies Kontingent erschöpft (maximal "
                f"{FREE_DAILY_LIMIT} Uploads pro Tag, verbleibend: {remaining}). Upgrade auf Premium für unbegrenzte Uploads."
            )
            return render_workspace(db_session, user, error_message=msg), 403

        saved = 0
        for file_storage in files:
            uploaded = save_file(
                db_session,
                file_storage,
                folder_label,
                request.remote_addr,
                user_id=user.id,
            )
            if uploaded:
                saved += 1
        if saved == 0:
            db_session.rollback()
            return render_workspace(db_session, user, error_message="Es konnte nichts gespeichert werden."), 400
        db_session.commit()
    except Exception:  # noqa: BLE001
        db_session.rollback()
        return render_workspace(db_session, user, error_message="Speichern fehlgeschlagen."), 500
    finally:
        db_session.close()

    return redirect(url_for("my_uploads", success="upload_saved"))

@app.route("/upload-namensliste", methods=["GET", "POST"])
def upload_namensliste():
    if request.method == "GET":
        return redirect(url_for("app_home"))

    file_storage = request.files.get("namensliste")
    if not file_storage or file_storage.filename == "":
        return redirect(url_for("app_home", message="Bitte wähle eine Excel-Datei aus."))

    try:
        names = parse_excel_names(file_storage)
    except ValueError as exc:
        return redirect(url_for("app_home", message=str(exc)))
    except Exception:  # noqa: BLE001
        return redirect(
            url_for(
                "app_home",
                message="Die Namensliste konnte nicht verarbeitet werden. Bitte das offizielle Template verwenden.",
            )
        )

    db_session = get_session()
    folder_label = sanitize_folder_label(Path(file_storage.filename).stem)
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        allowed, remaining = enforce_quota(db_session, user, 1)
        if not allowed:
            msg = (
                "Freies Kontingent erschöpft (maximal "
                f"{FREE_DAILY_LIMIT} Uploads pro Tag, verbleibend: {remaining}). Upgrade auf Premium für unbegrenzte Uploads."
            )
            return render_workspace(db_session, user, error_message=msg), 403

        file_storage.stream.seek(0)
        uploaded = save_file(db_session, file_storage, folder_label, request.remote_addr, user_id=user.id)
        if not uploaded:
            db_session.rollback()
            return render_workspace(db_session, user, error_message="Es konnte nichts gespeichert werden."), 400
        add_person_rows(db_session, uploaded, names)
        db_session.commit()
    except Exception:  # noqa: BLE001
        db_session.rollback()
        return render_workspace(db_session, user, error_message="Die Namensliste konnte nicht gespeichert werden.")
    finally:
        db_session.close()

    return redirect(url_for("my_uploads", success="namensliste_saved"))


@app.route("/my/uploads")
def my_uploads():
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        uploads = fetch_user_uploads(db_session, user.id)
        theme = get_theme(user)
        ensure_csrf_token()
        success_message = success_text_from_query(request.args.get("success"))
        error_message = error_text_from_query(request.args.get("error")) or request.args.get("message")
        return render_template(
            "my_uploads.html",
            uploads=uploads,
            user=user,
            theme=theme,
            success_message=success_message,
            error_message=error_message,
            csrf_token=flask_session.get("csrf_token"),
            datetime=datetime,
        )
    finally:
        db_session.close()


@app.route("/download/<int:upload_id>")
def download(upload_id: int):
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        upload_obj = fetch_upload(db_session, upload_id)
        if not upload_obj:
            abort(404)
        if upload_obj.user_id != user.id and not user.is_admin:
            return redirect(url_for("my_uploads", error="unauthorized")), 403
    finally:
        db_session.close()

    file_path = BASE_DIR / upload_obj.server_path
    if not file_path.exists():
        abort(404)

    return send_file(file_path, as_attachment=True, download_name=Path(upload_obj.original_filename).name)


@app.route("/delete/<int:upload_id>", methods=["POST"])
def delete_upload(upload_id: int):
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))

        token = flask_session.get("csrf_token")
        if not token or request.form.get("csrf_token") != token:
            return redirect(url_for("my_uploads", error="unauthorized")), 403

        upload_obj = fetch_upload(db_session, upload_id)
        if not upload_obj:
            abort(404)
        if upload_obj.user_id != user.id and not user.is_admin:
            return redirect(url_for("my_uploads", error="unauthorized")), 403

        file_path = BASE_DIR / upload_obj.server_path
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                pass
        db_session.delete(upload_obj)
        db_session.commit()
    finally:
        db_session.close()

    return redirect(url_for("my_uploads", success="deleted"))


@app.route("/admin/uploads")
def admin_uploads():
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))
        if not user.is_admin:
            return redirect(url_for("app_home", error="unauthorized")), 403

        uploads = fetch_uploads_desc(db_session)
        theme = get_theme(user)
    finally:
        db_session.close()
    return render_template("admin_uploads.html", uploads=uploads, theme=theme)


@app.route("/admin/uploads/<int:upload_id>")
def admin_upload_detail(upload_id: int):
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))
        if not user.is_admin:
            return redirect(url_for("app_home", error="unauthorized")), 403

        upload_obj = fetch_upload(db_session, upload_id)
        if not upload_obj:
            abort(404)
        theme = get_theme(user)
    finally:
        db_session.close()
    return render_template("admin_upload_detail.html", upload=upload_obj, theme=theme)


@app.route("/admin")
def admin_panel():
    db_session = get_session()
    try:
        user = require_user(db_session)
        if not user:
            return redirect(url_for("landing", error="login_required"))
        if not user.is_admin:
            return redirect(url_for("app_home", error="unauthorized")), 403

        total_uploads = len(fetch_uploads_desc(db_session))
        total_users = db_session.query(User).count()
        theme = get_theme(user)
    finally:
        db_session.close()

    return render_template(
        "admin_panel.html",
        total_uploads=total_uploads,
        total_users=total_users,
        theme=theme,
    )


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
