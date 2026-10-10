"""Shared SQLAlchemy storage. SQLite locally; PostgreSQL in deployment."""
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, LargeBinary, String, Text, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def uid():
    return uuid.uuid4().hex


def now():
    return datetime.now(timezone.utc).isoformat()


ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('REVIEW_DATA_DIR', str(ROOT / 'data')))
DATABASE_URL = os.getenv('DATABASE_URL', f'sqlite:///{DATA / "review.db"}')
if DATABASE_URL.startswith('sqlite'):
    DATA.mkdir(parents=True, exist_ok=True)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False, 'timeout': 30} if DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
if DATABASE_URL.startswith('sqlite'):
    @event.listens_for(engine, 'connect')
    def sqlite_settings(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA journal_mode=WAL')

Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default='member')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class LoginSession(Base):
    __tablename__ = 'login_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)


class AccessGate(Base):
    __tablename__ = 'access_gate'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    passphrase_hash: Mapped[str] = mapped_column(Text)


class AccessSession(Base):
    __tablename__ = 'access_sessions'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[int] = mapped_column(Integer)


class Workspace(Base):
    __tablename__ = 'workspace'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(100), default='FineSub 知识库')
    serial: Mapped[int] = mapped_column(Integer, default=0)
    profile: Mapped[str] = mapped_column(String(40), default='legacy-preserve')
    latest_release: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Entry(Base):
    __tablename__ = 'entries'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    path: Mapped[str] = mapped_column(String(500), unique=True)
    current_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    published_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Revision(Base):
    __tablename__ = 'revisions'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    entry_id: Mapped[str] = mapped_column(ForeignKey('entries.id'), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    base_published: Mapped[str | None] = mapped_column(String(32), nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    number: Mapped[int] = mapped_column(Integer)
    path: Mapped[str] = mapped_column(String(500))
    group_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(80), default='')
    aliases: Mapped[str] = mapped_column(Text, default='')
    summary: Mapped[str] = mapped_column(Text, default='')
    source: Mapped[str] = mapped_column(Text, default='')
    operation: Mapped[str] = mapped_column(String(20), default='upsert')
    status: Mapped[str] = mapped_column(String(24), default='pending')
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Batch(Base):
    __tablename__ = 'batches'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(24), default='queued')
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Asset(Base):
    __tablename__ = 'assets'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey('batches.id'), index=True)
    filename: Mapped[str] = mapped_column(String(500))
    digest: Mapped[str] = mapped_column(String(64))
    data: Mapped[bytes] = mapped_column(LargeBinary)


class ImportItem(Base):
    __tablename__ = 'import_items'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    batch_id: Mapped[str] = mapped_column(ForeignKey('batches.id'), index=True)
    path: Mapped[str] = mapped_column(String(500))
    origin_path: Mapped[str] = mapped_column(String(500), default='')
    grouped: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[str] = mapped_column(Text)
    base_revision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    operation: Mapped[str] = mapped_column(String(20), default='upsert')
    classification: Mapped[str] = mapped_column(String(24))
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default='')


class Review(Base):
    __tablename__ = 'reviews'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    revision_id: Mapped[str] = mapped_column(ForeignKey('revisions.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey('reviews.id'), nullable=True)
    verdict: Mapped[str] = mapped_column(String(24))
    body: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, default='')
    suggestion: Mapped[str] = mapped_column(Text, default='')
    evidence: Mapped[str] = mapped_column(Text, default='')
    resolution: Mapped[str] = mapped_column(String(24), default='open')
    resolution_note: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Decision(Base):
    __tablename__ = 'decisions'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    revision_id: Mapped[str] = mapped_column(ForeignKey('revisions.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Release(Base):
    __tablename__ = 'releases'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default='')
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    parent_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    rollback_of: Mapped[str | None] = mapped_column(String(32), nullable=True)
    profile: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default='queued')
    report: Mapped[dict] = mapped_column(JSON, default=dict)
    artifact: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    archive: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(24))
    target_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), default='queued', index=True)
    error: Mapped[str] = mapped_column(Text, default='')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    touched_at: Mapped[str] = mapped_column(String(40), default=now)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Notice(Base):
    __tablename__ = 'notices'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    entry_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    actor_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target_id: Mapped[str] = mapped_column(String(80), default='')
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(40), default=now)


def init_db():
    Base.metadata.create_all(engine)
    # Additive migration for the initial development schema; never drops data.
    with engine.begin() as connection:
        columns = {c['name'] for c in inspect(connection).get_columns('entries')}
        if 'published_revision' not in columns:
            connection.execute(text('ALTER TABLE entries ADD COLUMN published_revision VARCHAR(32)'))
        columns = {c['name'] for c in inspect(connection).get_columns('releases')}
        if 'changes' not in columns:
            connection.execute(text("ALTER TABLE releases ADD COLUMN changes JSON NOT NULL DEFAULT '[]'"))
    with Session.begin() as db:
        if not db.get(Workspace, 1):
            db.add(Workspace(id=1))
