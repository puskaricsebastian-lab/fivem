import io
import mimetypes
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.datastructures import FileStorage
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from models import (
    File,
    User,
    add_file,
    create_user,
    get_file,
    get_session,
    get_user_by_email,
    get_user_by_username,
    init_db,
    list_files,
    remove_session,
    toggle_favorite,
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_ROOT = Path(os.environ.get("UPLOAD_ROOT", "/opt/htl-upload/uploads"))
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me")

login_manager = LoginManager(app)
login_manager.login_view = "auth"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
USERNAME_RE = re.compile(r"^[a-z0-9_-]{3,20}$")


def sanitize_username(username: str) -> str | None:
    username = (username or "").strip().lower()
    if USERNAME_RE.match(username):
        return username
    return None


def sanitize_rel_path(rel_path: str | None) -> str:
    if not rel_path:
        return ""
    parts: List[str] = []
    for raw in Path(rel_path).parts:
        if raw in {"..", ".", ""}:
            continue
        safe = re.sub(r"[^a-zA-Z0-9._-]", "-", raw).strip("-")
        if safe:
            parts.append(safe)
    return "/".join(parts)


def ensure_user_root(username: str) -> Path:
    root = UPLOAD_ROOT / username
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_join_user_path(username: str, rel_path: str, filename: str | None = None) -> Path:
    root = ensure_user_root(username)
    clean_rel = sanitize_rel_path(rel_path)
    target = root / clean_rel
    if filename:
        target = target / filename
    resolved = target.resolve()
    if not str(resolved).startswith(str(root.resolve())):
        raise ValueError("Unsafe path")
    return resolved


def list_subfolders(username: str, rel_path: str) -> List[str]:
    base = safe_join_user_path(username, rel_path)
    base.mkdir(parents=True, exist_ok=True)
    return sorted([p.name for p in base.iterdir() if p.is_dir()])


def human_size(num: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < 1024:
            return f"{num:.1f} {unit}" if unit != "B" else f"{num} B"
        num /= 1024
    return f"{num:.1f} PB"


def current_session():
    return get_session()


@login_manager.user_loader
def load_user(user_id: str):
    if not user_id:
        return None
    with current_session() as session:
        return session.get(User, int(user_id))


@app.teardown_appcontext
def cleanup(_exc):
    # ensure scoped sessions are removed
    remove_session()


# ---------------------------------------------------------------------------
# auth views
# ---------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def auth():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("auth.html", view="login")


@app.route("/register", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    email = (request.form.get("email") or "").strip()
    username_raw = request.form.get("username") or ""
    password = request.form.get("password") or ""
    password2 = request.form.get("password_repeat") or ""

    username = sanitize_username(username_raw)
    errors = {}

    if not email or "@" not in email:
        errors["email"] = "Bitte eine gültige E-Mail angeben."
    if not username:
        errors["username"] = "Username 3-20 Zeichen, a-z, 0-9, _ oder -."
    if password != password2:
        errors["password_repeat"] = "Passwörter stimmen nicht überein."
    if not valid_password(password):
        errors["password"] = "Passwort zu schwach (min 8, Groß/Klein, Zahl)."

    with current_session() as session:
        if email and get_user_by_email(session, email):
            errors["email"] = "E-Mail wird bereits verwendet."
        if username and get_user_by_username(session, username):
            errors["username"] = "Username ist vergeben."

        if errors:
            return render_template("auth.html", view="register", errors=errors, values=request.form), 400

        pw_hash = generate_password_hash(password)
        user = create_user(session, email=email, username=username, password_hash=pw_hash)
        session.commit()
        login_user(user)
        flash("Registrierung erfolgreich. Willkommen!", "success")
        return redirect(url_for("dashboard"))


@app.route("/login", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    errors = {}

    with current_session() as session:
        user = get_user_by_email(session, email) if email else None
        if not user or not check_password_hash(user.password_hash, password):
            errors["global"] = "Login-Daten ungültig."
        if errors:
            return render_template("auth.html", view="login", errors=errors, values=request.form), 401
        login_user(user)
        flash("Willkommen zurück!", "success")
        return redirect(url_for("dashboard"))


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Abgemeldet.", "info")
    return redirect(url_for("auth"))


# ---------------------------------------------------------------------------
# dashboard & files
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    with current_session() as session:
        files, _ = list_files(session, current_user.id, per_page=10)
        return render_template("dashboard.html", recent=files)


@app.route("/files")
@login_required
def files_view():
    rel_path = sanitize_rel_path(request.args.get("path"))
    search = request.args.get("search") or None
    type_filter = request.args.get("type") or None
    date_filter = request.args.get("date") or None
    favorites_only = request.args.get("favorites") == "1"
    sort = request.args.get("sort") or None
    page = int(request.args.get("page", 1))
    per_page = 25
    try:
        subfolders = list_subfolders(current_user.username, rel_path)
    except ValueError:
        abort(400)
    with current_session() as session:
        files, total = list_files(
            session,
            current_user.id,
            rel_path=rel_path or None,
            search=search,
            type_filter=type_filter,
            date_filter=date_filter,
            favorites_only=favorites_only,
            sort=sort,
            page=page,
            per_page=per_page,
        )
    breadcrumbs = rel_path.split("/") if rel_path else []
    return render_template(
        "files.html",
        files=files,
        rel_path=rel_path,
        breadcrumbs=breadcrumbs,
        subfolders=subfolders,
        search=search or "",
        favorites_only=favorites_only,
        type_filter=type_filter or "",
        date_filter=date_filter or "",
        sort=sort or "",
        page=page,
        total=total,
        per_page=per_page,
        human_size=human_size,
    )


# ---------------------------------------------------------------------------
# upload & file actions
# ---------------------------------------------------------------------------
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "GET":
        rel_path = sanitize_rel_path(request.args.get("path"))
        return render_template("upload.html", rel_path=rel_path)

    rel_path = sanitize_rel_path(request.form.get("path"))
    files: List[FileStorage] = request.files.getlist("files")
    if not files:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(url_for("upload", path=rel_path))

    user_root = ensure_user_root(current_user.username)
    try:
        target_dir = safe_join_user_path(current_user.username, rel_path)
    except ValueError:
        abort(400)
    target_dir.mkdir(parents=True, exist_ok=True)

    with current_session() as session:
        for storage in files:
            filename = secure_filename(storage.filename or "")
            if not filename:
                continue
            dest = target_dir / filename
            storage.save(dest)
            size = dest.stat().st_size
            mime_type = storage.mimetype or mimetypes.guess_type(filename)[0]
            add_file(
                session,
                user_id=current_user.id,
                rel_path=rel_path,
                filename=filename,
                size_bytes=size,
                mime_type=mime_type,
            )
        session.commit()
    flash("Upload abgeschlossen.", "success")
    return redirect(url_for("files_view", path=rel_path))


@app.route("/download/<int:file_id>")
@login_required
def download(file_id: int):
    with current_session() as session:
        file = get_file(session, file_id)
        if not file or file.user_id != current_user.id:
            abort(404)
        try:
            path = safe_join_user_path(current_user.username, file.rel_path, file.filename)
        except ValueError:
            abort(400)
        if not path.exists():
            abort(404)
        return send_file(path, as_attachment=True, download_name=file.filename)


@app.route("/preview/<int:file_id>")
@login_required
def preview(file_id: int):
    with current_session() as session:
        file = get_file(session, file_id)
        if not file or file.user_id != current_user.id:
            abort(404)
        try:
            path = safe_join_user_path(current_user.username, file.rel_path, file.filename)
        except ValueError:
            abort(400)
        if not path.exists():
            abort(404)
        mime = file.mime_type or mimetypes.guess_type(file.filename)[0]
        return send_file(path, mimetype=mime or "application/octet-stream", as_attachment=False)


@app.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete(file_id: int):
    with current_session() as session:
        file = get_file(session, file_id)
        if not file or file.user_id != current_user.id:
            abort(404)
        try:
            path = safe_join_user_path(current_user.username, file.rel_path, file.filename)
        except ValueError:
            abort(400)
        if path.exists():
            path.unlink()
        session.delete(file)
        session.commit()
    flash("Datei gelöscht.", "success")
    return redirect(url_for("files_view", path=request.form.get("return_path", "")))


@app.route("/favorite/<int:file_id>", methods=["POST"])
@login_required
def favorite(file_id: int):
    with current_session() as session:
        file = get_file(session, file_id)
        if not file or file.user_id != current_user.id:
            abort(404)
        toggle_favorite(session, file)
        session.commit()
        status = "favorisiert" if file.is_favorite else "entfernt"
        flash(f"Favorit {status}.", "success")
    return redirect(request.referrer or url_for("files_view"))


@app.route("/bulk/delete", methods=["POST"])
@login_required
def bulk_delete():
    ids = request.form.getlist("file_ids")
    if not ids:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(request.referrer or url_for("files_view"))
    with current_session() as session:
        for raw_id in ids:
            file = get_file(session, int(raw_id))
            if file and file.user_id == current_user.id:
                try:
                    path = safe_join_user_path(current_user.username, file.rel_path, file.filename)
                except ValueError:
                    continue
                if path.exists():
                    path.unlink()
                session.delete(file)
        session.commit()
    flash("Dateien gelöscht.", "success")
    return redirect(request.referrer or url_for("files_view"))


@app.route("/bulk/download", methods=["POST"])
@login_required
def bulk_download():
    ids = request.form.getlist("file_ids")
    if not ids:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(request.referrer or url_for("files_view"))
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        with current_session() as session:
            for raw_id in ids:
                file = get_file(session, int(raw_id))
                if not file or file.user_id != current_user.id:
                    continue
                try:
                    path = safe_join_user_path(current_user.username, file.rel_path, file.filename)
                except ValueError:
                    continue
                if path.exists():
                    arcname = f"{file.rel_path}/{file.filename}" if file.rel_path else file.filename
                    zf.write(path, arcname=arcname)
    mem.seek(0)
    return send_file(mem, mimetype="application/zip", as_attachment=True, download_name="export.zip")


@app.route("/bulk/move", methods=["POST"])
@login_required
def bulk_move():
    ids = request.form.getlist("file_ids")
    target = sanitize_rel_path(request.form.get("target") or "")
    if target == "..":
        target = ""
    if target is None:
        target = ""
    if not ids:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(request.referrer or url_for("files_view"))
    try:
        target_dir = safe_join_user_path(current_user.username, target)
    except ValueError:
        abort(400)
    target_dir.mkdir(parents=True, exist_ok=True)
    with current_session() as session:
        for raw_id in ids:
            file = get_file(session, int(raw_id))
            if not file or file.user_id != current_user.id:
                continue
            try:
                src = safe_join_user_path(current_user.username, file.rel_path, file.filename)
            except ValueError:
                continue
            dest = target_dir / file.filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.exists():
                src.replace(dest)
            file.rel_path = target
        session.commit()
    flash("Dateien verschoben.", "success")
    return redirect(url_for("files_view", path=target))


# ---------------------------------------------------------------------------
# folder management
# ---------------------------------------------------------------------------
@app.route("/folders/create", methods=["POST"])
@login_required
def create_folder():
    base_path = sanitize_rel_path(request.form.get("path"))
    name_raw = request.form.get("name") or ""
    name = sanitize_rel_path(name_raw)
    if not name:
        flash("Ordnername ungültig.", "error")
        return redirect(request.referrer or url_for("files_view"))
    try:
        target = safe_join_user_path(current_user.username, base_path, name)
    except ValueError:
        abort(400)
    target.mkdir(parents=True, exist_ok=True)
    flash("Ordner erstellt.", "success")
    new_rel = "/".join([p for p in [base_path, name] if p])
    return redirect(url_for("files_view", path=new_rel))


@app.route("/folders/delete", methods=["POST"])
@login_required
def delete_folder():
    rel_path = sanitize_rel_path(request.form.get("path"))
    if not rel_path:
        flash("Kein Ordner gewählt.", "error")
        return redirect(request.referrer or url_for("files_view"))
    try:
        target = safe_join_user_path(current_user.username, rel_path)
    except ValueError:
        abort(400)
    if any(target.iterdir()):
        flash("Ordner ist nicht leer.", "error")
        return redirect(request.referrer or url_for("files_view"))
    target.rmdir()
    flash("Ordner gelöscht.", "success")
    parent = "/".join(rel_path.split("/")[:-1])
    return redirect(url_for("files_view", path=parent))


@app.route("/folders/rename", methods=["POST"])
@login_required
def rename_folder():
    rel_path = sanitize_rel_path(request.form.get("path"))
    new_name = sanitize_rel_path(request.form.get("name"))
    if not rel_path or not new_name:
        flash("Ungültige Angaben.", "error")
        return redirect(request.referrer or url_for("files_view"))
    try:
        src = safe_join_user_path(current_user.username, rel_path)
    except ValueError:
        abort(400)
    if any(src.iterdir()):
        flash("Nur leere Ordner können umbenannt werden.", "error")
        return redirect(request.referrer or url_for("files_view"))
    parent = src.parent
    dest = parent / new_name
    src.rename(dest)
    parent_rel = "/".join(rel_path.split("/")[:-1])
    updated_rel = "/".join([p for p in [parent_rel, new_name] if p])
    flash("Ordner umbenannt.", "success")
    return redirect(url_for("files_view", path=updated_rel))


# ---------------------------------------------------------------------------
# utils
# ---------------------------------------------------------------------------

def valid_password(password: str) -> bool:
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    return True


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


init_db()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
