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
    UniqueConstraint,
    create_engine,
    func,
    inspect,
    text,
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
    rel_path = Column(String(1024), nullable=True)
    size_bytes = Column(Integer, nullable=False)
    content_type = Column(String(255), nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploader_ip = Column(String(255), nullable=True)

    uploader = relationship("User", back_populates="uploads")
    persons = relationship("Person", back_populates="upload", cascade="all, delete-orphan", lazy="joined")
    group_links = relationship("GroupUpload", back_populates="upload", cascade="all, delete-orphan")


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
    username = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    plan = Column(String(50), default="free", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    daily_uploads_count = Column(Integer, default=0, nullable=False)
    daily_uploads_date = Column(Date, nullable=True)
    trial_expires_at = Column(DateTime, nullable=True)
    theme = Column(String(20), default="dark", nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)

    uploads = relationship("Upload", back_populates="uploader")
    shares_created = relationship("Share", back_populates="owner", foreign_keys="Share.owner_id")
    shares_received = relationship("Share", back_populates="target_user", foreign_keys="Share.target_user_id")
    memberships = relationship("GroupMembership", back_populates="user")
    groups_administered = relationship("Group", back_populates="admin", foreign_keys="Group.admin_id")


class Share(Base):
    __tablename__ = "shares"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", back_populates="shares_created", foreign_keys=[owner_id])
    target_user = relationship("User", back_populates="shares_received", foreign_keys=[target_user_id])
    upload = relationship("Upload")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    join_code = Column(String(20), unique=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    admin = relationship("User", back_populates="groups_administered", foreign_keys=[admin_id])
    memberships = relationship("GroupMembership", back_populates="group", cascade="all, delete-orphan")
    uploads = relationship("GroupUpload", back_populates="group", cascade="all, delete-orphan")


class GroupMembership(Base):
    __tablename__ = "group_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), default="member", nullable=False)
    status = Column(String(50), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group", back_populates="memberships")
    user = relationship("User", back_populates="memberships")


class GroupUpload(Base):
    __tablename__ = "group_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(Integer, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group", back_populates="uploads")
    upload = relationship("Upload", back_populates="group_links")
    uploader = relationship("User")


class EmailVerification(Base):
    __tablename__ = "email_verifications"
    __table_args__ = (UniqueConstraint("user_id", name="uq_verification_user"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    last_sent_at = Column(DateTime, nullable=True)


def _ensure_username_column():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "username" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(255)"))

    with SessionLocal() as session:
        for user in session.query(User).all():
            user.username = f"user-{user.id}"
        session.commit()


def _ensure_email_verified_column():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "email_verified" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"))


def _ensure_rel_path_column():
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("uploads")}
    if "rel_path" in columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE uploads ADD COLUMN rel_path VARCHAR(1024)"))

    with SessionLocal() as session:
        for upload in session.query(Upload).all():
            upload.rel_path = upload.server_path
        session.commit()


def init_db() -> None:
    Base.metadata.create_all(engine)
    _ensure_username_column()
    _ensure_email_verified_column()
    _ensure_rel_path_column()


def get_session() -> Session:
    return SessionLocal()


def fetch_recent_uploads(session: Session, limit: int = 25) -> List[Upload]:
    return (
        session.query(Upload)
        .order_by(Upload.upload_timestamp.desc())
        .limit(limit)
        .all()
    )


def fetch_user_uploads(
    session: Session,
    user_id: int,
    *,
    limit: int | None = None,
    sort: str | None = None,
) -> List[Upload]:
    query = session.query(Upload).filter(Upload.user_id == user_id)

    if sort == "name_asc":
        query = query.order_by(Upload.original_filename.asc())
    elif sort == "name_desc":
        query = query.order_by(Upload.original_filename.desc())
    elif sort == "size_asc":
        query = query.order_by(Upload.size_bytes.asc())
    elif sort == "size_desc":
        query = query.order_by(Upload.size_bytes.desc())
    elif sort == "date_asc":
        query = query.order_by(Upload.upload_timestamp.asc())
    else:
        query = query.order_by(Upload.upload_timestamp.desc())

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


def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return (
        session.query(User)
        .filter(func.lower(User.username) == username.lower())
        .one_or_none()
    )


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.query(User).filter(User.id == user_id).one_or_none()


def create_user(
    session: Session,
    *,
    email: str,
    username: str,
    password_hash: str,
    plan: str = "free",
) -> User:
    user = User(email=email, username=username, password_hash=password_hash, plan=plan)
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


def user_storage_usage(session: Session, user_id: int) -> int:
    total = (
        session.query(func.coalesce(func.sum(Upload.size_bytes), 0))
        .filter(Upload.user_id == user_id)
        .scalar()
    )
    return int(total or 0)


def reset_daily_counter_if_needed(user: User) -> None:
    today = date.today()
    if user.daily_uploads_date != today:
        user.daily_uploads_date = today
        user.daily_uploads_count = 0


def create_share(session: Session, *, owner_id: int, target_user_id: int, upload_id: int) -> Share:
    share = Share(owner_id=owner_id, target_user_id=target_user_id, upload_id=upload_id)
    session.add(share)
    session.flush()
    return share


def get_share(session: Session, share_id: int) -> Share | None:
    return session.query(Share).filter(Share.id == share_id).one_or_none()


def list_shares_by_owner(session: Session, owner_id: int) -> List[Share]:
    return (
        session.query(Share)
        .filter(Share.owner_id == owner_id)
        .order_by(Share.created_at.desc())
        .all()
    )


def list_shares_for_user(session: Session, user_id: int) -> List[Share]:
    return (
        session.query(Share)
        .filter(Share.target_user_id == user_id)
        .order_by(Share.created_at.desc())
        .all()
    )


def delete_share(session: Session, share: Share) -> None:
    session.delete(share)


def create_group(
    session: Session, *, name: str, description: str | None, join_code: str, admin_id: int
) -> Group:
    group = Group(name=name, description=description, join_code=join_code, admin_id=admin_id)
    session.add(group)
    session.flush()
    return group


def get_group_by_id(session: Session, group_id: int) -> Group | None:
    return session.query(Group).filter(Group.id == group_id).one_or_none()


def get_group_by_code(session: Session, join_code: str) -> Group | None:
    return session.query(Group).filter(func.lower(Group.join_code) == join_code.lower()).one_or_none()


def list_groups_for_user(session: Session, user_id: int) -> List[Group]:
    membership_sub = (
        session.query(GroupMembership.group_id)
        .filter(GroupMembership.user_id == user_id, GroupMembership.status == "accepted")
        .subquery()
    )
    return (
        session.query(Group)
        .filter((Group.admin_id == user_id) | (Group.id.in_(membership_sub)))
        .order_by(Group.created_at.desc())
        .all()
    )


def get_membership(session: Session, group_id: int, user_id: int) -> GroupMembership | None:
    return (
        session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id, GroupMembership.user_id == user_id)
        .one_or_none()
    )


def create_membership(session: Session, *, group_id: int, user_id: int, status: str = "pending") -> GroupMembership:
    membership = GroupMembership(group_id=group_id, user_id=user_id, status=status)
    session.add(membership)
    session.flush()
    return membership


def list_pending_requests(session: Session, group_id: int) -> List[GroupMembership]:
    return (
        session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id, GroupMembership.status == "pending")
        .order_by(GroupMembership.created_at.asc())
        .all()
    )


def list_group_members(session: Session, group_id: int) -> List[GroupMembership]:
    return (
        session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id, GroupMembership.status == "accepted")
        .order_by(GroupMembership.created_at.asc())
        .all()
    )


def update_membership_status(session: Session, membership: GroupMembership, status: str) -> None:
    membership.status = status


def add_group_upload(
    session: Session, *, group_id: int, upload_id: int, uploader_id: int
) -> GroupUpload:
    link = GroupUpload(group_id=group_id, upload_id=upload_id, uploader_id=uploader_id)
    session.add(link)
    session.flush()
    return link


def list_group_uploads(session: Session, group_id: int) -> List[GroupUpload]:
    return (
        session.query(GroupUpload)
        .filter(GroupUpload.group_id == group_id)
        .order_by(GroupUpload.created_at.desc())
        .all()
    )


def upsert_email_verification(
    session: Session,
    *,
    user_id: int,
    code_hash: str,
    expires_at: datetime,
    sent_at: datetime,
) -> None:
    existing = (
        session.query(EmailVerification)
        .filter(EmailVerification.user_id == user_id)
        .one_or_none()
    )
    if existing:
        existing.code_hash = code_hash
        existing.expires_at = expires_at
        existing.attempts = 0
        existing.last_sent_at = sent_at
    else:
        session.add(
            EmailVerification(
                user_id=user_id,
                code_hash=code_hash,
                expires_at=expires_at,
                attempts=0,
                last_sent_at=sent_at,
            )
        )


def get_verification(session: Session, user_id: int) -> EmailVerification | None:
    return (
        session.query(EmailVerification)
        .filter(EmailVerification.user_id == user_id)
        .one_or_none()
    )
