"""Ortak test fikstürleri.

Testler gerçek Postgres GEREKTİRMEZ; kimlik doğrulama için bellek-içi SQLite
kullanan bir DB override'ı enjekte edilir. Arama motoru yalnız-sparse'tır
(build_dense=False → embedding modeli yüklenmez). API testleri lifespan'i
tetiklemeden hem motoru hem de DB bağımlılığını doğrudan enjekte eder.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.ratelimit import reset_buckets
from app.db import get_db
from app.main import app
from app.models import Base, User
from app.services.auth import create_access_token, hash_password
from app.services.memory_store import FaultRecord, MemoryEngine


@pytest.fixture(autouse=True)
def _clear_rate_limit_buckets():
    """Her testten önce rate-limit kovalarını temizle (testler arası izolasyon).

    TestClient tüm istekleri aynı IP'den (testclient) yapar; kovalar süreç
    boyunca paylaşıldığı için temizlenmezse testler 429'a takılabilir.
    """
    reset_buckets()
    yield
    reset_buckets()


def _records() -> list[FaultRecord]:
    """Bilinen kategoriler/DTC kodlarıyla küçük, deterministik test seti."""
    rows = [
        ("r1", "Fren pedalı titriyor ve gıcırtı sesi geliyor", "Fren", "C0035"),
        ("r2", "Fren yaparken araç sarsılıyor ve titreşim oluyor", "Fren", "C0040"),
        ("r3", "Motor rölantide tekliyor ve sarsıntı var", "Motor", "P0300"),
        ("r4", "Klima soğutmuyor, kompresör devreye girmiyor", "Klima", "P0645"),
        ("r5", "Direksiyon ağırlaştı, park ederken zor dönüyor", "Direksiyon", "C1513"),
    ]
    return [
        FaultRecord(
            id=rid,
            description=desc,
            category=cat,
            dtc_code=dtc,
            vehicle_model="Test Aracı",
            mileage_km=100_000,
            solution=f"{cat} için çözüm uygulandı",
        )
        for rid, desc, cat, dtc in rows
    ]


@pytest.fixture
def records() -> list[FaultRecord]:
    return _records()


@pytest.fixture
def engine(records) -> MemoryEngine:
    """Yalnız-sparse motor (model yüklemez, deterministik)."""
    return MemoryEngine(records, build_dense=False)


@pytest.fixture
def db_session():
    """Test başına bellek-içi SQLite oturumu (auth uçları için).

    StaticPool + tek bağlantı sayesinde aynı in-memory veritabanı, isteğin
    açtığı tüm oturumlarda paylaşılır.
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Yalnız User tablosunu oluştur (pgvector'a bağımlı tabloları SQLite kuramaz).
    User.__table__.create(bind=test_engine, checkfirst=True)
    TestingSession = sessionmaker(
        bind=test_engine, autocommit=False, autoflush=False, class_=Session
    )
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine, tables=[User.__table__])
        test_engine.dispose()


@pytest.fixture
def seeded_admin(db_session) -> User:
    """DB'ye bir admin kullanıcı ekle ve döndür."""
    user = User(
        username="test_admin",
        password_hash=hash_password("admin123"),
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(seeded_admin) -> str:
    """Seedlenmiş admin için geçerli bir JWT."""
    return create_access_token(sub=str(seeded_admin.id), role=seeded_admin.role)


@pytest.fixture
def auth_headers(admin_token) -> dict[str, str]:
    """Korunan uçlara eklenecek Authorization başlığı."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def client(engine, db_session, auth_headers) -> TestClient:
    """Motoru + DB override'ı enjekte edilmiş, jeton başlıklı TestClient.

    Mevcut entegrasyon testleri korunan uçlara çarptığı için varsayılan
    Authorization başlığı admin jetonuyla doldurulur (testler kırılmasın).
    """
    app.state.engine = engine
    app.state.feedback = []

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass  # oturum yaşam döngüsü db_session fikstürüne ait.

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    test_client.headers.update(auth_headers)
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def anon_client(engine, db_session) -> TestClient:
    """Kimlik doğrulamasız (jetonsuz) TestClient — 401/403 testleri için."""
    app.state.engine = engine
    app.state.feedback = []

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
