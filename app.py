import io
import mimetypes
import os
import re
import secrets
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
    Friend,
    Group,
    GroupMembership,
    GroupUpload,
    Message,
    Share,
    User,
    add_message,
    add_file,
    add_group_upload,
    create_group,
    create_user,
    create_friend_request,
    create_membership,
    create_share,
    delete_share,
    find_group_by_code,
    find_friendship,
    get_file,
    get_group,
    get_membership,
    get_session,
    get_user_by_email,
    get_user_by_username,
    init_db,
    list_files,
    list_group_uploads,
    list_groups_for_user,
    list_messages_between,
    list_friend_requests,
    list_outgoing_requests,
    list_friends,
    list_memberships,
    list_shares_for_owner,
    list_shares_for_target,
    remove_session,
    set_membership_status,
    set_friend_status,
    toggle_favorite,
    user_can_access_file,
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


def random_join_code() -> str:
    return "#" + secrets.token_hex(3).upper()


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


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    errors = {}
    if request.method == "POST":
        current_pw = request.form.get("current_password") or ""
        new_pw = request.form.get("new_password") or ""
        repeat_pw = request.form.get("new_password_repeat") or ""
        if not check_password_hash(current_user.password_hash, current_pw):
            errors["current_password"] = "Aktuelles Passwort ist falsch."
        if not valid_password(new_pw):
            errors["new_password"] = "Passwort zu schwach (min 8, Groß/Klein, Zahl)."
        if new_pw != repeat_pw:
            errors["new_password_repeat"] = "Passwörter stimmen nicht überein."
        if not errors:
            with current_session() as session:
                user = session.get(User, current_user.id)
                user.password_hash = generate_password_hash(new_pw)
                session.commit()
            flash("Passwort aktualisiert.", "success")
            return redirect(url_for("profile"))
    return render_template("profile.html", errors=errors)


# ---------------------------------------------------------------------------
# dashboard & files
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    with current_session() as session:
        files, _ = list_files(session, current_user.id, per_page=10)
        return render_template("dashboard.html", recent=files, human_size=human_size)


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
        group_id = request.args.get("group_id")
        return render_template("upload.html", rel_path=rel_path, group_id=group_id)

    rel_path = sanitize_rel_path(request.form.get("path"))
    files: List[FileStorage] = request.files.getlist("files")
    group_id_raw = request.form.get("group_id")
    group = None
    if not files:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(url_for("upload", path=rel_path))

    with current_session() as session:
        if group_id_raw:
            group = get_group(session, int(group_id_raw))
            if not group:
                abort(404)
            membership = get_membership(session, group.id, current_user.id)
            if not (group.admin_id == current_user.id or (membership and membership.status == "accepted")):
                flash("Keine Berechtigung für diesen Gruppen-Upload.", "error")
                return redirect(url_for("dashboard"))

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
            file = add_file(
                session,
                user_id=current_user.id,
                rel_path=rel_path,
                filename=filename,
                size_bytes=size,
                mime_type=mime_type,
            )
            if group:
                add_group_upload(session, group_id=group.id, upload_id=file.id, uploader_id=current_user.id)
        session.commit()
    flash("Upload abgeschlossen.", "success")
    return redirect(url_for("files_view", path=rel_path))


@app.route("/download/<int:file_id>")
@login_required
def download(file_id: int):
    with current_session() as session:
        file = get_file(session, file_id)
        if not file or not user_can_access_file(session, current_user.id, file):
            abort(404)
        owner = file.user.username if file.user else current_user.username
        try:
            path = safe_join_user_path(owner, file.rel_path, file.filename)
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
        if not file or not user_can_access_file(session, current_user.id, file):
            abort(404)
        owner = file.user.username if file.user else current_user.username
        try:
            path = safe_join_user_path(owner, file.rel_path, file.filename)
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


@app.route("/bulk/zip", methods=["POST"])
@login_required
def bulk_zip():
    ids = request.form.getlist("file_ids")
    rel_path = sanitize_rel_path(request.form.get("return_path") or "")
    if not ids:
        flash("Keine Dateien ausgewählt.", "error")
        return redirect(request.referrer or url_for("files_view"))
    try:
        target_dir = safe_join_user_path(current_user.username, rel_path)
    except ValueError:
        abort(400)
    target_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"bundle-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.zip"
    zip_path = target_dir / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
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
            size = zip_path.stat().st_size
            add_file(
                session,
                user_id=current_user.id,
                rel_path=rel_path,
                filename=zip_name,
                size_bytes=size,
                mime_type="application/zip",
            )
            session.commit()
    flash("ZIP erstellt.", "success")
    return redirect(url_for("files_view", path=rel_path))


# ---------------------------------------------------------------------------
# shares
# ---------------------------------------------------------------------------


@app.route("/shares/new", methods=["GET", "POST"])
@login_required
def shares_new():
    with current_session() as session:
        own_files, _ = list_files(session, current_user.id, per_page=200)
        if request.method == "GET":
            preselect = request.args.get("file_id")
            values = {"file_id": preselect} if preselect else None
            return render_template("shares_new.html", files=own_files, values=values)

        target_username = sanitize_username(request.form.get("target_username") or "")
        file_id_raw = request.form.get("file_id")
        errors = {}
        target_user = get_user_by_username(session, target_username) if target_username else None
        if not target_user:
            errors["target_username"] = "Benutzer nicht gefunden."
        file = get_file(session, int(file_id_raw)) if file_id_raw else None
        if not file or file.user_id != current_user.id:
            errors["file_id"] = "Ungültige Datei."
        if errors:
            return render_template("shares_new.html", files=own_files, errors=errors, values=request.form), 400
        create_share(session, owner_id=current_user.id, target_user_id=target_user.id, file_id=file.id)
        session.commit()
        flash("Freigabe erstellt.", "success")
        return redirect(url_for("shares_mine"))


@app.route("/shares/mine")
@login_required
def shares_mine():
    with current_session() as session:
        shares = list_shares_for_owner(session, current_user.id)
        return render_template("shares_mine.html", shares=shares)


@app.route("/shared-with-me")
@login_required
def shared_with_me():
    with current_session() as session:
        shares = list_shares_for_target(session, current_user.id)
        return render_template("shared_with_me.html", shares=shares)


# ---------------------------------------------------------------------------
# friends & chat
# ---------------------------------------------------------------------------


@app.route("/friends", methods=["GET", "POST"])
@login_required
def friends():
    errors = {}
    with current_session() as session:
        if request.method == "POST":
            username = sanitize_username(request.form.get("username") or "")
            if not username:
                errors["username"] = "Ungültiger Benutzername."
            else:
                target = get_user_by_username(session, username)
                if not target:
                    errors["username"] = "Benutzer nicht gefunden."
                elif target.id == current_user.id:
                    errors["username"] = "Du kannst dich nicht selbst hinzufügen."
                else:
                    existing = find_friendship(session, current_user.id, target.id)
                    if existing:
                        errors["username"] = "Anfrage besteht bereits."
                    else:
                        create_friend_request(session, requester_id=current_user.id, addressee_id=target.id)
                        session.commit()
                        flash("Freundschaftsanfrage gesendet.", "success")
                        return redirect(url_for("friends"))
        incoming = list_friend_requests(session, current_user.id)
        outgoing = list_outgoing_requests(session, current_user.id)
        accepted = list_friends(session, current_user.id)
    return render_template("friends.html", errors=errors, incoming=incoming, outgoing=outgoing, accepted=accepted)


@app.route("/friends/<int:friend_id>/<action>", methods=["POST"])
@login_required
def friends_action(friend_id: int, action: str):
    if action not in {"accept", "reject", "cancel"}:
        abort(400)
    with current_session() as session:
        friend = session.get(Friend, friend_id)
        if not friend:
            abort(404)
        if action in {"accept", "reject"} and friend.addressee_id != current_user.id:
            abort(403)
        if action == "cancel" and friend.requester_id != current_user.id:
            abort(403)
        status = "accepted" if action == "accept" else "rejected"
        set_friend_status(session, friend_id, status)
        session.commit()
    flash("Status aktualisiert.", "success")
    return redirect(url_for("friends"))


@app.route("/chat/<int:user_id>", methods=["GET", "POST"])
@login_required
def chat(user_id: int):
    with current_session() as session:
        other = session.get(User, user_id)
        if not other:
            abort(404)
        friendship = find_friendship(session, current_user.id, other.id)
        if not friendship or friendship.status != "accepted":
            abort(403)
        if request.method == "POST":
            content = (request.form.get("message") or "").strip()
            file_id = request.form.get("file_id")
            file_ref = None
            if file_id:
                file_ref = get_file(session, int(file_id))
                if not file_ref or file_ref.user_id != current_user.id:
                    abort(403)
                existing_share = (
                    session.query(Share)
                    .filter(
                        Share.file_id == file_ref.id,
                        Share.owner_id == current_user.id,
                        Share.target_user_id == other.id,
                    )
                    .one_or_none()
                )
                if not existing_share:
                    create_share(
                        session,
                        owner_id=current_user.id,
                        target_user_id=other.id,
                        file_id=file_ref.id,
                    )
            add_message(
                session,
                sender_id=current_user.id,
                receiver_id=other.id,
                content=content,
                file_id=file_ref.id if file_ref else None,
            )
            session.commit()
            flash("Nachricht gesendet.", "success")
            return redirect(url_for("chat", user_id=other.id))
        messages = list_messages_between(session, current_user.id, other.id)
        own_files, _ = list_files(session, current_user.id, per_page=100)
    return render_template("chat.html", other=other, messages=messages, own_files=own_files, human_size=human_size)


@app.route("/shares/<int:share_id>/delete", methods=["POST"])
@login_required
def delete_share_view(share_id: int):
    with current_session() as session:
        success = delete_share(session, share_id, current_user.id)
        if success:
            session.commit()
            flash("Freigabe entfernt.", "success")
        else:
            flash("Freigabe nicht gefunden.", "error")
    return redirect(request.referrer or url_for("shares_mine"))


# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------


@app.route("/groups")
@login_required
def groups_overview():
    with current_session() as session:
        groups = list_groups_for_user(session, current_user.id)
        admin_groups = session.query(Group).filter(Group.admin_id == current_user.id).order_by(Group.name.asc()).all()
        return render_template("groups.html", groups=groups, admin_groups=admin_groups)


@app.route("/groups/new", methods=["GET", "POST"])
@login_required
def groups_new():
    if request.method == "GET":
        return render_template("group_new.html")
    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip()
    if not name:
        flash("Gruppenname erforderlich.", "error")
        return redirect(url_for("groups_new"))
    with current_session() as session:
        code = random_join_code()
        group = create_group(session, name=name, description=description, join_code=code, admin_id=current_user.id)
        # Admin direkt als accepted Mitglied
        create_membership(session, group_id=group.id, user_id=current_user.id, status="accepted")
        session.commit()
        flash("Gruppe erstellt.", "success")
        return redirect(url_for("group_detail", group_id=group.id))


@app.route("/groups/join", methods=["GET", "POST"])
@login_required
def groups_join():
    if request.method == "GET":
        return render_template("group_join.html")
    code = (request.form.get("code") or "").strip()
    with current_session() as session:
        group = find_group_by_code(session, code)
        if not group:
            flash("Gruppe nicht gefunden.", "error")
            return redirect(url_for("groups_join"))
        membership = get_membership(session, group.id, current_user.id)
        if membership:
            flash("Beitritt wurde bereits angefragt oder bestätigt.", "info")
            return redirect(url_for("group_detail", group_id=group.id))
        create_membership(session, group_id=group.id, user_id=current_user.id, status="pending")
        session.commit()
        flash("Beitrittsanfrage gesendet.", "success")
        return redirect(url_for("group_detail", group_id=group.id))


@app.route("/groups/<int:group_id>")
@login_required
def group_detail(group_id: int):
    with current_session() as session:
        group = get_group(session, group_id)
        if not group:
            abort(404)
        membership = get_membership(session, group.id, current_user.id)
        if not (group.admin_id == current_user.id or (membership and membership.status in {"accepted", "pending"})):
            abort(403)
        members = list_memberships(session, group.id, status="accepted")
        pending = list_memberships(session, group.id, status="pending") if group.admin_id == current_user.id else []
        uploads = list_group_uploads(session, group.id)
        return render_template(
            "group_detail.html",
            group=group,
            membership=membership,
            members=members,
            pending=pending,
            uploads=uploads,
            human_size=human_size,
        )


@app.route("/groups/<int:group_id>/requests/<int:membership_id>/<action>", methods=["POST"])
@login_required
def group_request_action(group_id: int, membership_id: int, action: str):
    with current_session() as session:
        group = get_group(session, group_id)
        if not group or group.admin_id != current_user.id:
            abort(403)
        if action not in {"accept", "reject"}:
            abort(400)
        status = "accepted" if action == "accept" else "rejected"
        set_membership_status(session, membership_id, status)
        session.commit()
        flash("Anfrage aktualisiert.", "success")
    return redirect(url_for("group_detail", group_id=group_id))


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
