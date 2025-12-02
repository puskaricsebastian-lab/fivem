import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
)
from sqlalchemy.orm import Session, declarative_base, relationship, scoped_session, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{BASE_DIR / 'database.db'}"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    server_path = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploader_ip = Column(String(255), nullable=True)

    uploader = relationship("User", back_populates="uploads")
    persons = relationship("Person", back_populates="upload", cascade="all, delete-orphan", lazy="joined")


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    vorname = Column(String(255), nullable=False)
    nachname = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    upload = relationship("Upload", back_populates="persons")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    plan = Column(String(50), default="free", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    daily_uploads_count = Column(Integer, default=0, nullable=False)
    daily_uploads_date = Column(Date, nullable=True)
    trial_expires_at = Column(DateTime, nullable=True)
    theme = Column(String(20), default="dark", nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)

    uploads = relationship("Upload", back_populates="uploader")


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()


def fetch_recent_uploads(session: Session, limit: int = 25) -> List[Upload]:
    return (
        session.query(Upload)
        .order_by(Upload.upload_timestamp.desc())
        .limit(limit)
        .all()
    )


def fetch_user_uploads(session: Session, user_id: int, limit: int | None = None) -> List[Upload]:
    query = (
        session.query(Upload)
        .filter(Upload.user_id == user_id)
        .order_by(Upload.upload_timestamp.desc())
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def fetch_uploads_desc(session: Session) -> List[Upload]:
    return session.query(Upload).order_by(Upload.upload_timestamp.desc()).all()


def fetch_upload(session: Session, upload_id: int) -> Upload | None:
    return session.query(Upload).filter(Upload.id == upload_id).one_or_none()


def fetch_upload_for_user(session: Session, upload_id: int, user_id: int) -> Upload | None:
    return (
        session.query(Upload)
        .filter(Upload.id == upload_id, Upload.user_id == user_id)
        .one_or_none()
    )


def add_upload(
    session: Session,
    *,
    user_id: int,
    original_filename: str,
    server_path: str,
    size_bytes: int,
    content_type: str,
    uploader_ip: str | None = None,
) -> Upload:
    upload = Upload(
        user_id=user_id,
        original_filename=original_filename,
        server_path=server_path,
        size_bytes=size_bytes,
        content_type=content_type,
        uploader_ip=uploader_ip,
        upload_timestamp=datetime.utcnow(),
    )
    session.add(upload)
    session.flush()  # ensures id is available
    return upload


def add_person_rows(session: Session, upload: Upload, names: Iterable[dict]) -> None:
    people = [
        Person(upload_id=upload.id, vorname=item["vorname"], nachname=item["nachname"])
        for item in names
    ]
    session.add_all(people)


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    return session.query(User).filter(func.lower(User.email) == email.lower()).one_or_none()


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.query(User).filter(User.id == user_id).one_or_none()


def create_user(session: Session, email: str, password_hash: str, plan: str = "free") -> User:
    user = User(email=email, password_hash=password_hash, plan=plan)
    session.add(user)
    session.flush()
    return user


def count_uploads_for_date(session: Session, user_id: int, target_date: date) -> int:
    start = datetime.combine(target_date, datetime.min.time())
    end = start + timedelta(days=1)
    return (
        session.query(func.count(Upload.id))
        .filter(Upload.user_id == user_id, Upload.upload_timestamp >= start, Upload.upload_timestamp < end)
        .scalar()
    )


def reset_daily_counter_if_needed(user: User) -> None:
    today = date.today()
    if user.daily_uploads_date != today:
        user.daily_uploads_date = today
        user.daily_uploads_count = 0
