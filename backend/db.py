"""Explicitly configured storage. Schema changes belong to Alembic, never startup."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import DateTime, Integer, JSON, String, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

SCHEMA_REVISION = '0001_saved_portfolios'


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class SavedPortfolio(Base):
    __tablename__ = 'saved_portfolios'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(String(2000), nullable=False, default='')
    definition: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, 'postgresql'), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    __mapper_args__ = {'version_id_col': version}


class Database:
    def __init__(self, url):
        kwargs = {'pool_pre_ping': True}
        if url.startswith('sqlite'):
            kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 5}
        elif url.startswith('postgresql+psycopg://'):
            kwargs['connect_args'] = {'connect_timeout': 5, 'options': '-c statement_timeout=10000'}
        else:
            raise ValueError('Use a postgresql+psycopg or sqlite SQLAlchemy database URL')
        self.engine = create_engine(url, **kwargs)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def dispose(self):
        self.engine.dispose()
