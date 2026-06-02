"""İki aşamalı retrieval'ın ikinci aşaması: cross-encoder ile yeniden sıralama.

Bi-encoder (dense) + BM25 hızlı ama kaba bir aday listesi (top-N) üretir;
cross-encoder her (sorgu, aday) çiftini BİRLİKTE kodlayarak çok daha isabetli
bir alaka skoru verir. Bu, klasik "retrieve-then-rerank" mimarisidir ve
precision@k üzerinde ölçülebilir kazanç sağlar.

Model yüklenemezse (çevrimdışı/disk) rerank sessizce devre dışı kalır ve
aday listesi olduğu gibi döner — sistem hâlâ çalışır (graceful degradation).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# Çok dilli (Türkçe destekli) MS MARCO cross-encoder reranker.
RERANK_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MAX_LENGTH = 256


@lru_cache(maxsize=1)
def _get_model() -> "CrossEncoder | None":
    """Cross-encoder'ı tek sefer yükle; başarısızsa None döndür."""
    try:
        from sentence_transformers import CrossEncoder

        return CrossEncoder(RERANK_MODEL, max_length=MAX_LENGTH)
    except Exception as exc:  # model yok / çevrimdışı
        print(f"[rerank] cross-encoder yüklenemedi, rerank kapalı: {exc}")
        return None


def is_available() -> bool:
    """Reranker kullanılabilir mi (model yüklenebiliyor mu)?"""
    return _get_model() is not None


def _sigmoid(x: float) -> float:
    """Cross-encoder logit'ini 0-1 güven skoruna sıkıştır."""
    return 1.0 / (1.0 + math.exp(-x))


def rerank_scores(query: str, documents: list[str]) -> list[float] | None:
    """Her (sorgu, doküman) çifti için sigmoid-normalize alaka skoru.

    Model yoksa None döner (çağıran taraf aday sırasını korur).
    """
    model = _get_model()
    if model is None or not documents:
        return None
    pairs = [(query, doc) for doc in documents]
    raw = model.predict(pairs)
    return [_sigmoid(float(s)) for s in raw]
