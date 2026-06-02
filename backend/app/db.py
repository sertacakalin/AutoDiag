"""Veritabanı bağlantı yönetimi ve başlatma."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Base

settings = get_settings()

# pool_pre_ping: bağlantı kopmuşsa sessizce yenile (Docker'da db geç kalkarsa faydalı).
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI bağımlılığı: istek başına bir oturum aç, sonunda kapat."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """pgvector uzantısını kur ve tüm tabloları oluştur.

    CREATE EXTENSION, Vector tipini kullanan tabloları oluşturmadan ÖNCE
    çalışmalıdır; aksi halde "type vector does not exist" hatası alınır.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    Base.metadata.create_all(bind=engine)
