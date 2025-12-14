import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, create_engine, func, inspect
from sqlalchemy.orm import Session, declarative_base, relationship, scoped_session, sessionmaker
from flask_login import UserMixin

BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'database.db'}"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()


class User(Base, UserMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    files = relationship("File", back_populates="user", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rel_path = Column(String(1024), nullable=False, default="")
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(255), nullable=True)
    is_favorite = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="files")


# --- schema helpers -------------------------------------------------------

def drop_legacy_tables() -> None:
    inspector = inspect(engine)
    legacy_tables = [
        "email_verifications",
        "shares",
        "group_uploads",
        "group_memberships",
        "groups",
        "persons",
    ]
    with engine.begin() as conn:
        for table in legacy_tables:
            if inspector.has_table(table):
                conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table}")


def init_db() -> None:
    # Drop legacy tables that are no longer used
    drop_legacy_tables()
    Base.metadata.create_all(engine)
    migrate_from_uploads()


def get_session() -> Session:
    return SessionLocal()


def remove_session() -> None:
    SessionLocal.remove()


# --- queries --------------------------------------------------------------

def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.query(User).filter(func.lower(User.email) == email.lower()).one_or_none()


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.query(User).filter(func.lower(User.username) == username.lower()).one_or_none()


def create_user(session: Session, *, email: str, username: str, password_hash: str) -> User:
    user = User(email=email, username=username, password_hash=password_hash)
    session.add(user)
    session.flush()
    return user


def add_file(
    session: Session,
    *,
    user_id: int,
    rel_path: str,
    filename: str,
    size_bytes: int,
    mime_type: str | None,
) -> File:
    file = File(
        user_id=user_id,
        rel_path=rel_path,
        filename=filename,
        size_bytes=size_bytes,
        mime_type=mime_type,
        created_at=datetime.utcnow(),
    )
    session.add(file)
    session.flush()
    return file


def get_file(session: Session, file_id: int) -> Optional[File]:
    return session.query(File).filter(File.id == file_id).one_or_none()


def list_files(
    session: Session,
    user_id: int,
    *,
    rel_path: str | None = None,
    search: str | None = None,
    type_filter: str | None = None,
    date_filter: str | None = None,
    favorites_only: bool = False,
    sort: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> Tuple[List[File], int]:
    query = session.query(File).filter(File.user_id == user_id)

    if rel_path:
        query = query.filter(File.rel_path == rel_path)
    if search:
        like_value = f"%{search.lower()}%"
        query = query.filter(func.lower(File.filename).like(like_value))
    if favorites_only:
        query = query.filter(File.is_favorite.is_(True))

    if type_filter == "image":
        query = query.filter(File.mime_type.ilike("image/%"))
    elif type_filter == "pdf":
        query = query.filter(File.mime_type.ilike("%pdf%"))
    elif type_filter == "zip":
        query = query.filter(File.mime_type.ilike("%zip%"))

    now = datetime.utcnow()
    if date_filter == "today":
        start = datetime(now.year, now.month, now.day)
        query = query.filter(File.created_at >= start)
    elif date_filter == "7d":
        cutoff = now - timedelta(days=7)
        query = query.filter(File.created_at >= cutoff)
    elif date_filter == "30d":
        cutoff = now - timedelta(days=30)
        query = query.filter(File.created_at >= cutoff)

    sort_map = {
        "name": File.filename.asc(),
        "name_desc": File.filename.desc(),
        "size": File.size_bytes.asc(),
        "size_desc": File.size_bytes.desc(),
        "date": File.created_at.desc(),
        "date_old": File.created_at.asc(),
    }
    if sort in sort_map:
        query = query.order_by(sort_map[sort])
    else:
        query = query.order_by(File.created_at.desc())

    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total


def toggle_favorite(session: Session, file: File) -> None:
    file.is_favorite = not file.is_favorite


def migrate_from_uploads() -> None:
    inspector = inspect(engine)
    if not inspector.has_table("uploads"):
        return
    with engine.begin() as conn:
        existing_files = conn.exec_driver_sql("SELECT COUNT(*) FROM files").scalar()
        if existing_files:
            return
        upload_rows = conn.exec_driver_sql(
            "SELECT id, user_id, original_filename, server_path, size_bytes, content_type, upload_timestamp FROM uploads"
        ).fetchall()
        for row in upload_rows:
            server_path = Path(row[3]) if row[3] else None
            rel_path = ""
            filename = row[2]
            if server_path:
                try:
                    rel_path = str(server_path.parent.relative_to(server_path.parents[1]))
                    filename = server_path.name
                except Exception:
                    rel_path = ""
                    filename = server_path.name if server_path.name else row[2]
            conn.exec_driver_sql(
                "INSERT INTO files (user_id, rel_path, filename, size_bytes, mime_type, created_at, is_favorite) VALUES (:user_id, :rel_path, :filename, :size_bytes, :mime_type, :created_at, 0)",
                {
                    "user_id": row[1],
                    "rel_path": rel_path,
                    "filename": filename,
                    "size_bytes": row[4],
                    "mime_type": row[5],
                    "created_at": row[6],
                },
            )
