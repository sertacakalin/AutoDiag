"""Hibrit arama: dense (pgvector cosine) + sparse (BM25) + DTC/kategori bonusu.

Dense ve sparse skorları ayrı ayrı min-max normalize edilip ağırlıklı toplanır;
DTC veya kategori eşleşmesi varsa küçük bonuslar eklenir (re-ranking).
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fault, FaultEmbedding
from app.services.embedding import embed, normalize_text

# Hibrit skor ağırlıkları ve re-ranking bonusları.
DENSE_W = 0.7
SPARSE_W = 0.3
DTC_BONUS = 0.10
CAT_BONUS = 0.05

# fault_embeddings.embedding için HNSW indeksi (üretimde performans için):
#   CREATE INDEX IF NOT EXISTS ix_fault_embeddings_hnsw
#     ON fault_embeddings USING hnsw (embedding vector_cosine_ops);


@dataclass
class Candidate:
    """Bir arama adayı; dense, sparse ve nihai skorları taşır."""

    fault: Fault
    dense: float = 0.0
    sparse: float = 0.0
    final: float = 0.0


def dense_search(db: Session, query: str, limit: int = 30) -> dict:
    """pgvector cosine mesafesiyle en yakın kayıtları getir.

    Dönüş: {fault_id: Candidate(fault, dense=similarity)}.
    similarity = 1 - cosine_distance (1.0 = birebir, 0.0 = alakasız).
    """
    query_vec = embed(query)
    distance = FaultEmbedding.embedding.cosine_distance(query_vec)

    stmt = (
        select(Fault, distance.label("distance"))
        .join(FaultEmbedding, FaultEmbedding.fault_id == Fault.id)
        .order_by(distance.asc())
        .limit(limit)
    )

    results: dict = {}
    for fault, dist in db.execute(stmt):
        results[fault.id] = Candidate(fault=fault, dense=1.0 - float(dist))
    return results


def sparse_search(db: Session, query: str, limit: int = 30) -> dict:
    """BM25 (anahtar kelime) ile en alakalı kayıtları getir.

    Dönüş: {fault_id: Candidate(fault, sparse=score)}.
    """
    faults = list(db.execute(select(Fault)).scalars())
    if not faults:
        return {}

    corpus = [normalize_text(f.description).split() for f in faults]
    bm25 = BM25Okapi(corpus)
    query_tokens = normalize_text(query).split()
    scores = bm25.get_scores(query_tokens)

    # En yüksek skordan limit kadarını al.
    ranked = sorted(zip(faults, scores), key=lambda x: x[1], reverse=True)[:limit]
    return {
        f.id: Candidate(fault=f, sparse=float(s))
        for f, s in ranked
        if s > 0
    }


def _minmax(candidates: dict, key: str) -> dict:
    """Adayların `key` skorunu 0-1 aralığına normalize et.

    Tek aday ya da tüm skorlar eşitse (aralık 0) sıfıra bölme olmaması için 1.0 verilir.
    """
    values = [getattr(c, key) for c in candidates.values()]
    if not values:
        return {}
    lo, hi = min(values), max(values)
    span = hi - lo
    return {
        fid: (1.0 if span == 0 else (getattr(c, key) - lo) / span)
        for fid, c in candidates.items()
    }


def hybrid_search(
    db: Session,
    query: str,
    top_k: int = 5,
    category: str | None = None,
    dtc_code: str | None = None,
) -> list[Candidate]:
    """Dense + sparse sonuçları birleştirip re-ranking ile top_k aday döndür."""
    dense = dense_search(db, query)
    sparse = sparse_search(db, query)

    dense_norm = _minmax(dense, "dense")
    sparse_norm = _minmax(sparse, "sparse")

    # Her iki aramadan gelen tüm fault_id'lerin birleşimi.
    all_ids = set(dense) | set(sparse)
    merged: dict = {}

    for fid in all_ids:
        cand = dense.get(fid) or sparse.get(fid)
        # Aynı fault hem dense hem sparse'ta varsa skorları tek Candidate'te topla.
        d_score = dense[fid].dense if fid in dense else 0.0
        s_score = sparse[fid].sparse if fid in sparse else 0.0
        d_norm = dense_norm.get(fid, 0.0)
        s_norm = sparse_norm.get(fid, 0.0)

        final = DENSE_W * d_norm + SPARSE_W * s_norm

        fault = cand.fault
        if dtc_code and fault.dtc_code and fault.dtc_code.upper() == dtc_code.upper():
            final += DTC_BONUS
        if category and fault.category == category:
            final += CAT_BONUS

        merged[fid] = Candidate(
            fault=fault, dense=d_score, sparse=s_score, final=final
        )

    ranked = sorted(merged.values(), key=lambda c: c.final, reverse=True)
    return ranked[:top_k]
