"""Ortak test fikstürleri.

Testler DB GEREKTİRMEZ ve hız/determinizm için yalnız-sparse motor kullanır
(build_dense=False → embedding modeli yüklenmez). API testleri lifespan'i
tetiklemeden motoru doğrudan enjekte eder.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.memory_store import FaultRecord, MemoryEngine


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
def client(engine) -> TestClient:
    """Motoru enjekte edilmiş TestClient (lifespan tetiklenmez)."""
    app.state.engine = engine
    app.state.feedback = []
    return TestClient(app)
