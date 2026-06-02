"""Üretim arama motoru: PostgreSQL + pgvector (DbEngine).

MemoryEngine ile AYNI arayüzü sunar (search/get/add/count/categories/mode), böylece
API katmanı değişmeden çalışır. Retrieval mantığı retrieval.hybrid_search'tedir
(dense pgvector cosine + BM25 + DTC/kategori bonusu). Sorgu genişletme ve
cross-encoder rerank, MemoryEngine ile aynı şekilde uygulanır.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import Fault, FaultEmbedding
from app.services.memory_store import FaultRecord, Hit
from app.services.retrieval import hybrid_search


def _to_record(fault: Fault) -> FaultRecord:
    """ORM Fault → FaultRecord (Hit/şema uyumu; id str'e çevrilir)."""
    return FaultRecord(
        id=str(fault.id),
        description=fault.description,
        category=fault.category,
        dtc_code=fault.dtc_code,
        vehicle_model=fault.vehicle_model,
        mileage_km=fault.mileage_km,
        solution=fault.solution,
    )


class DbEngine:
    """pgvector destekli üretim arama motoru."""

    mode = "db"

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    # --------------------------------------------------------------- meta
    @property
    def count(self) -> int:
        with self._session_factory() as db:
            return db.scalar(select(func.count()).select_from(Fault)) or 0

    @property
    def categories(self) -> list[str]:
        with self._session_factory() as db:
            rows = db.execute(select(Fault.category).distinct()).scalars()
            return sorted({c for c in rows if c})

    def get(self, fault_id: str) -> FaultRecord | None:
        with self._session_factory() as db:
            fault = db.get(Fault, fault_id)
            return _to_record(fault) if fault else None

    # --------------------------------------------------------------- yazma
    def add(self, record: FaultRecord) -> FaultRecord:
        from app.services.embedding import embed

        with self._session_factory() as db:
            fault = Fault(
                description=record.description, category=record.category,
                dtc_code=record.dtc_code, vehicle_model=record.vehicle_model,
                mileage_km=record.mileage_km, solution=record.solution,
            )
            db.add(fault)
            db.flush()
            db.add(FaultEmbedding(
                fault_id=fault.id, embedding=embed(record.description),
                model_version="runtime",
            ))
            db.commit()
            return _to_record(fault)

    # --------------------------------------------------------------- arama
    def search(
        self,
        query: str,
        top_k: int = 5,
        category: str | None = None,
        dtc_code: str | None = None,
        rerank: bool = False,
        expand: bool = False,
        pool_size: int = 30,
    ) -> list[Hit]:
        if expand:
            from app.services.query_norm import expand_query

            effective = expand_query(query)
        else:
            effective = query

        with self._session_factory() as db:
            candidates = hybrid_search(
                db, effective, top_k=max(top_k, pool_size),
                category=category, dtc_code=dtc_code,
            )
            hits = [
                Hit(
                    fault=_to_record(c.fault),
                    similarity=min(c.final, 1.0),
                    dense=c.dense, sparse=c.sparse,
                )
                for c in candidates
            ]

        if not rerank:
            return hits[:top_k]

        from app.services.rerank import rerank_scores

        pool = hits[: max(top_k, pool_size)]
        scores = rerank_scores(query, [h.fault.description for h in pool])
        if scores is None:
            return pool[:top_k]
        for hit, score in zip(pool, scores):
            hit.rerank_score = score
            hit.similarity = score
        pool.sort(key=lambda h: h.rerank_score or 0.0, reverse=True)
        return pool[:top_k]


def _db_reachable_and_populated(session_factory) -> bool:
    """DB erişilebilir ve dolu mu (>=1 kayıt)?"""
    try:
        with session_factory() as db:
            return (db.scalar(select(func.count()).select_from(Fault)) or 0) > 0
    except Exception:
        return False


def try_build_db_engine() -> "DbEngine | None":
    """DB erişilebilir ve doluysa DbEngine döndür; değilse None (MemoryEngine'e düş)."""
    try:
        from app.db import SessionLocal

        if _db_reachable_and_populated(SessionLocal):
            return DbEngine(SessionLocal)
    except Exception as exc:
        print(f"[db_engine] DB motoru kurulamadı, MemoryEngine'e düşülüyor: {exc}")
    return None
