"""DB'siz (bellek-içi) arama motoru — sunum/demo ve test için.

CSV'deki arıza kayıtlarını belleğe yükler ve `retrieval.py` ile *aynı* hibrit
skorlama mantığını (dense + sparse + DTC/kategori bonusu, min-max normalize,
ağırlıklı toplam) DB olmadan uygular. Postgres+pgvector hazır olduğunda
`DbEngine` devreye girer; bu motor üretim yolunun bire bir aynası olarak kalır.

Dense katman opsiyoneldir: embedding modeli yüklenemezse (örn. çevrimdışı)
motor zarifçe yalnızca-sparse (BM25) moduna düşer ve bunu `mode` ile bildirir.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from rank_bm25 import BM25Okapi

from app.services.embedding import normalize_text
from app.services.retrieval import (
    CAT_BONUS,
    DENSE_W,
    DTC_BONUS,
    SPARSE_W,
)


@dataclass(frozen=True)
class FaultRecord:
    """Bellekteki tek bir arıza kaydı (CSV satırı)."""

    id: str
    description: str
    category: str
    dtc_code: str | None
    vehicle_model: str | None
    mileage_km: int | None
    solution: str


@dataclass
class Hit:
    """Bir arama sonucu; nihai benzerlik ve bileşen skorlarını taşır.

    `rag.generate_suggestion` bu nesneden `similarity`, `description`,
    `solution` alanlarını okur (getattr ile), bu yüzden alan adları sabittir.
    `rerank_score` yalnız iki aşamalı arama (cross-encoder) açıkken doldurulur.
    """

    fault: FaultRecord
    similarity: float
    dense: float
    sparse: float
    rerank_score: float | None = None

    # rag.py'nin doğrudan eriştiği kısayollar.
    @property
    def description(self) -> str:
        return self.fault.description

    @property
    def solution(self) -> str:
        return self.fault.solution


def _to_int(value: str | None) -> int | None:
    """CSV'deki sayısal alanı güvenle int'e çevir (boşsa None)."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _clean(value: str | None) -> str | None:
    """Boş/whitespace alanı None'a indir."""
    if value is None:
        return None
    value = value.strip()
    return value or None


class MemoryEngine:
    """CSV destekli, bellek-içi hibrit arama motoru."""

    def __init__(self, faults: list[FaultRecord], build_dense: bool = True) -> None:
        self._faults: dict[str, FaultRecord] = {f.id: f for f in faults}
        self._order: list[str] = [f.id for f in faults]

        # Sparse (BM25) indeksi — her zaman kurulur, model gerektirmez.
        self._corpus = [normalize_text(f.description).split() for f in faults]
        self._bm25 = BM25Okapi(self._corpus) if self._corpus else None

        # Dense (vektör) katmanı — model yüklenebilirse kurulur.
        # build_dense=False: yalnız-sparse mod (test/düşük-kaynak; model yüklenmez).
        self._doc_vectors: list[list[float]] | None = None
        self._mode = "sparse"
        if build_dense:
            self._try_build_dense()

    # ----------------------------------------------------------------- kurulum
    def _try_build_dense(self) -> None:
        """Embedding modelini yükleyip doküman vektörlerini hesapla.

        Model indirilemez/yüklenemezse sessizce sparse moda kalınır.
        """
        try:
            from app.services.embedding import embed_batch

            descriptions = [self._faults[fid].description for fid in self._order]
            self._doc_vectors = embed_batch(descriptions)
            self._mode = "hybrid"
        except Exception as exc:  # model yok / çevrimdışı → sparse fallback
            print(f"[memory_store] dense katman kapalı (sparse moda düşüldü): {exc}")
            self._doc_vectors = None
            self._mode = "sparse"

    @classmethod
    def from_csv(cls, path: str | Path) -> "MemoryEngine":
        """CSV dosyasından motoru oluştur."""
        records: list[FaultRecord] = []
        with open(path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                description = _clean(row.get("description"))
                solution = _clean(row.get("solution"))
                category = _clean(row.get("category"))
                if not (description and solution and category):
                    continue  # eksik zorunlu alan → satırı atla
                records.append(
                    FaultRecord(
                        id=str(uuid4()),
                        description=description,
                        category=category,
                        dtc_code=_clean(row.get("dtc_code")),
                        vehicle_model=_clean(row.get("vehicle_model")),
                        mileage_km=_to_int(row.get("mileage_km")),
                        solution=solution,
                    )
                )
        return cls(records)

    # --------------------------------------------------------------- özellikler
    @property
    def mode(self) -> str:
        """Aktif arama modu: 'hybrid' (dense+sparse) veya 'sparse'."""
        return self._mode

    @property
    def count(self) -> int:
        """Yüklü arıza kaydı sayısı."""
        return len(self._faults)

    @property
    def categories(self) -> list[str]:
        """Verideki benzersiz kategoriler (alfabetik)."""
        return sorted({f.category for f in self._faults.values()})

    def get(self, fault_id: str) -> FaultRecord | None:
        """Tek bir kaydı id ile getir."""
        return self._faults.get(fault_id)

    # ------------------------------------------------------------------- yazma
    def add(self, record: FaultRecord) -> FaultRecord:
        """Yeni kayıt ekle ve indeksleri yeniden kur (küçük veri için ucuz)."""
        self._faults[record.id] = record
        self._order.append(record.id)
        self._rebuild()
        return record

    def _rebuild(self) -> None:
        """Kayıt eklenince BM25 ve dense indekslerini güncelle."""
        ordered = [self._faults[fid] for fid in self._order]
        self._corpus = [normalize_text(f.description).split() for f in ordered]
        self._bm25 = BM25Okapi(self._corpus) if self._corpus else None
        if self._mode == "hybrid":
            self._try_build_dense()

    # ------------------------------------------------------------------- arama
    def _dense_scores(self, query: str) -> dict[str, float]:
        """Sorgu vektörü ile her dokümanın kosinüs benzerliği (vektörler birim normlu)."""
        if self._doc_vectors is None:
            return {}
        from app.services.embedding import embed

        q = embed(query)
        scores: dict[str, float] = {}
        for fid, doc_vec in zip(self._order, self._doc_vectors):
            # Birim normlu vektörlerde nokta çarpımı = kosinüs benzerliği.
            scores[fid] = sum(a * b for a, b in zip(q, doc_vec))
        return scores

    def _sparse_scores(self, query: str) -> dict[str, float]:
        """BM25 skorları (yalnız pozitif olanlar)."""
        if self._bm25 is None:
            return {}
        tokens = normalize_text(query).split()
        raw = self._bm25.get_scores(tokens)
        return {
            fid: float(score)
            for fid, score in zip(self._order, raw)
            if score > 0
        }

    @staticmethod
    def _minmax(scores: dict[str, float]) -> dict[str, float]:
        """Skorları 0-1 aralığına normalize et (retrieval._minmax ile aynı kural)."""
        if not scores:
            return {}
        values = scores.values()
        lo, hi = min(values), max(values)
        span = hi - lo
        return {
            fid: (1.0 if span == 0 else (s - lo) / span)
            for fid, s in scores.items()
        }

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
        """İki aşamalı arama (opsiyonel sorgu genişletme ile).

        0. aşama (opsiyonel): sorgu genişletme — argo/günlük dili kanonik otomotiv
           terimleriyle zenginleştirir (domain gap'i kapatır). Yalnız 1. aşamayı
           besler; rerank doğal (orijinal) sorguyu kullanır.
        1. aşama (geri çağırma): hibrit skor (dense + sparse + bonus) ile en iyi
           `pool_size` aday. retrieval.hybrid_search ile aynı skorlama mantığı.
        2. aşama (yeniden sıralama, opsiyonel): cross-encoder ile aday havuzunu
           yeniden sırala; benzerlik skoru rerank güvenine güncellenir.
        """
        if expand:
            from app.services.query_norm import expand_query

            effective = expand_query(query)
        else:
            effective = query

        dense = self._dense_scores(effective)
        sparse = self._sparse_scores(effective)

        dense_norm = self._minmax(dense)
        sparse_norm = self._minmax(sparse)

        all_ids = set(dense) | set(sparse)
        hits: list[Hit] = []

        for fid in all_ids:
            fault = self._faults[fid]
            final = DENSE_W * dense_norm.get(fid, 0.0) + SPARSE_W * sparse_norm.get(
                fid, 0.0
            )
            if dtc_code and fault.dtc_code and fault.dtc_code.upper() == dtc_code.upper():
                final += DTC_BONUS
            if category and fault.category == category:
                final += CAT_BONUS

            hits.append(
                Hit(
                    fault=fault,
                    similarity=min(final, 1.0),  # gösterim için 0-1'e kırp
                    dense=dense.get(fid, 0.0),
                    sparse=sparse.get(fid, 0.0),
                )
            )

        hits.sort(key=lambda h: h.similarity, reverse=True)

        if not rerank:
            return hits[:top_k]

        # 2. aşama: aday havuzunu cross-encoder ile yeniden sırala.
        pool = hits[: max(top_k, pool_size)]
        from app.services.rerank import rerank_scores

        scores = rerank_scores(query, [h.fault.description for h in pool])
        if scores is None:  # reranker yok → 1. aşama sırası korunur
            return pool[:top_k]

        for hit, score in zip(pool, scores):
            hit.rerank_score = score
            hit.similarity = score  # gösterimde rerank güvenini yansıt
        pool.sort(key=lambda h: h.rerank_score or 0.0, reverse=True)
        return pool[:top_k]
