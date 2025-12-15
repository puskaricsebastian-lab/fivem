import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    inspect,
)
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


class Share(Base):
    __tablename__ = "shares"
    __table_args__ = (
        UniqueConstraint("owner_id", "target_user_id", "file_id", name="uq_share_owner_target_file"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    owner = relationship("User", foreign_keys=[owner_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
    file = relationship("File")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True)
    join_code = Column(String(16), unique=True, nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    admin = relationship("User", foreign_keys=[admin_id])


class GroupMembership(Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group")
    user = relationship("User")


class GroupUpload(Base):
    __tablename__ = "group_uploads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False)
    upload_id = Column(Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    group = relationship("Group")
    upload = relationship("File")
    uploader = relationship("User")


class Friend(Base):
    __tablename__ = "friends"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friend_pair"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    requester_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    addressee_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sender_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])
    file = relationship("File")


# --- schema helpers -------------------------------------------------------

def init_db() -> None:
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


# --- sharing ---------------------------------------------------------------

def create_share(session: Session, *, owner_id: int, target_user_id: int, file_id: int) -> Share:
    share = Share(owner_id=owner_id, target_user_id=target_user_id, file_id=file_id)
    session.add(share)
    session.flush()
    return share


def list_shares_for_owner(session: Session, owner_id: int) -> List[Share]:
    return (
        session.query(Share)
        .filter(Share.owner_id == owner_id)
        .order_by(Share.created_at.desc())
        .all()
    )


def list_shares_for_target(session: Session, user_id: int) -> List[Share]:
    return (
        session.query(Share)
        .filter(Share.target_user_id == user_id)
        .order_by(Share.created_at.desc())
        .all()
    )


def delete_share(session: Session, share_id: int, owner_id: int) -> bool:
    share = session.query(Share).filter(Share.id == share_id, Share.owner_id == owner_id).one_or_none()
    if share:
        session.delete(share)
        session.flush()
        return True
    return False


def user_can_access_file(session: Session, user_id: int, file: File) -> bool:
    if file.user_id == user_id:
        return True
    shared = (
        session.query(Share)
        .filter(Share.file_id == file.id, Share.target_user_id == user_id)
        .first()
    )
    if shared:
        return True
    group_links = (
        session.query(GroupUpload)
        .join(GroupMembership, GroupMembership.group_id == GroupUpload.group_id)
        .filter(
            GroupUpload.upload_id == file.id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "accepted",
        )
        .count()
    )
    return group_links > 0


# --- groups ----------------------------------------------------------------

def create_group(session: Session, *, name: str, description: str | None, join_code: str, admin_id: int) -> Group:
    group = Group(name=name, description=description, join_code=join_code, admin_id=admin_id)
    session.add(group)
    session.flush()
    return group


def get_group(session: Session, group_id: int) -> Optional[Group]:
    return session.get(Group, group_id)


def find_group_by_code(session: Session, code: str) -> Optional[Group]:
    return session.query(Group).filter(func.lower(Group.join_code) == code.lower()).one_or_none()


def create_membership(session: Session, *, group_id: int, user_id: int, status: str = "pending") -> GroupMembership:
    membership = GroupMembership(group_id=group_id, user_id=user_id, status=status)
    session.add(membership)
    session.flush()
    return membership


def get_membership(session: Session, group_id: int, user_id: int) -> Optional[GroupMembership]:
    return (
        session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id, GroupMembership.user_id == user_id)
        .one_or_none()
    )


def list_memberships(session: Session, group_id: int, status: str | None = None) -> List[GroupMembership]:
    query = session.query(GroupMembership).filter(GroupMembership.group_id == group_id)
    if status:
        query = query.filter(GroupMembership.status == status)
    return query.order_by(GroupMembership.created_at.desc()).all()


def set_membership_status(session: Session, membership_id: int, status: str) -> None:
    membership = session.get(GroupMembership, membership_id)
    if membership:
        membership.status = status
        session.flush()


def add_group_upload(session: Session, *, group_id: int, upload_id: int, uploader_id: int) -> GroupUpload:
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


def list_groups_for_user(session: Session, user_id: int) -> List[Group]:
    return (
        session.query(Group)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .filter(GroupMembership.user_id == user_id, GroupMembership.status == "accepted")
        .order_by(Group.name.asc())
        .all()
    )


# --- friends & messages ------------------------------------------------------


def find_friendship(session: Session, user_a: int, user_b: int) -> Optional[Friend]:
    return (
        session.query(Friend)
        .filter(
            ((Friend.requester_id == user_a) & (Friend.addressee_id == user_b))
            | ((Friend.requester_id == user_b) & (Friend.addressee_id == user_a))
        )
        .one_or_none()
    )


def create_friend_request(session: Session, *, requester_id: int, addressee_id: int) -> Friend:
    friend = Friend(requester_id=requester_id, addressee_id=addressee_id, status="pending")
    session.add(friend)
    session.flush()
    return friend


def list_friend_requests(session: Session, user_id: int) -> List[Friend]:
    return (
        session.query(Friend)
        .filter(Friend.addressee_id == user_id, Friend.status == "pending")
        .order_by(Friend.created_at.desc())
        .all()
    )


def list_outgoing_requests(session: Session, user_id: int) -> List[Friend]:
    return (
        session.query(Friend)
        .filter(Friend.requester_id == user_id, Friend.status == "pending")
        .order_by(Friend.created_at.desc())
        .all()
    )


def list_friends(session: Session, user_id: int) -> List[Friend]:
    return (
        session.query(Friend)
        .filter(
            (Friend.status == "accepted")
            & ((Friend.requester_id == user_id) | (Friend.addressee_id == user_id))
        )
        .order_by(Friend.created_at.desc())
        .all()
    )


def set_friend_status(session: Session, friendship_id: int, status: str) -> Optional[Friend]:
    friend = session.get(Friend, friendship_id)
    if friend:
        friend.status = status
        session.flush()
    return friend


def list_messages_between(session: Session, user_a: int, user_b: int, limit: int = 200) -> List[Message]:
    return (
        session.query(Message)
        .filter(
            ((Message.sender_id == user_a) & (Message.receiver_id == user_b))
            | ((Message.sender_id == user_b) & (Message.receiver_id == user_a))
        )
        .order_by(Message.created_at.asc())
        .limit(limit)
        .all()
    )


def add_message(
    session: Session, *, sender_id: int, receiver_id: int, content: str | None, file_id: int | None
) -> Message:
    msg = Message(
        sender_id=sender_id,
        receiver_id=receiver_id,
        content=content or "",
        file_id=file_id,
        created_at=datetime.utcnow(),
    )
    session.add(msg)
    session.flush()
    return msg


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
