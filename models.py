import os
from datetime import datetime
from typing import Iterable, List

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, relationship, scoped_session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL ist nicht gesetzt. Bitte Umgebungsvariable konfigurieren (z.B. postgres://...)")

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))
Base = declarative_base()


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    original_filename = Column(String(255), nullable=False)
    server_path = Column(String(1024), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploader_ip = Column(String(255), nullable=True)

    persons = relationship("Person", back_populates="upload", cascade="all, delete-orphan", lazy="joined")


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    vorname = Column(String(255), nullable=False)
    nachname = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    upload = relationship("Upload", back_populates="persons")


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


def fetch_uploads_desc(session: Session) -> List[Upload]:
    return session.query(Upload).order_by(Upload.upload_timestamp.desc()).all()


def fetch_upload(session: Session, upload_id: int) -> Upload | None:
    return session.query(Upload).filter(Upload.id == upload_id).one_or_none()


def add_upload(
    session: Session,
    *,
    original_filename: str,
    server_path: str,
    size_bytes: int,
    content_type: str,
    uploader_ip: str | None = None,
) -> Upload:
    upload = Upload(
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
