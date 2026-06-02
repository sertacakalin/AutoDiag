"""Metin → çok dilli yoğun (dense) vektör embedding servisi.

Model sadece ilk çağrıda yüklenir (lazy + lru_cache). Modülü import etmek
ağır bir yükleme tetiklemez.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# Çok dilli (Türkçe destekli) model; 384 boyutlu vektör üretir.
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

_WHITESPACE_RE = re.compile(r"\s+")


@lru_cache(maxsize=1)
def _get_model() -> "SentenceTransformer":
    """SentenceTransformer'ı tek sefer yükle ve önbelleğe al.

    EMBEDDING_MODEL="adapted" verilirse yerel domain-adapte model
    (models/autodiag-embed-tr) kullanılır; yoksa base modele düşülür.
    """
    # Import burada: modül import edilince torch/model yüklenmesin.
    from pathlib import Path

    from sentence_transformers import SentenceTransformer

    model_name = get_settings().EMBEDDING_MODEL or MODEL_NAME
    if model_name == "adapted":
        # En iyi mevcut domain-adapte model: Türkçe-native+adapte > MiniLM-adapte.
        # backend/app/services/embedding.py → parents[3] = autodiag kökü
        models_dir = Path(__file__).resolve().parents[3] / "models"
        for cand in ("autodiag-embed-tr-hn", "autodiag-embed-tr-trmteb", "autodiag-embed-tr"):
            path = models_dir / cand
            if path.exists():
                print(f"[embedding] domain-adapte model kullanılıyor: {cand}")
                return SentenceTransformer(str(path))
        print("[embedding] 'adapted' istendi ama model yok; base modele düşülüyor.")
        model_name = MODEL_NAME
    return SentenceTransformer(model_name)


def normalize_text(text: str) -> str:
    """Küçük harfe çevir ve fazla boşlukları tek boşluğa indir.

    Türkçe karakterler (ç, ğ, ı, ö, ş, ü) KORUNUR.
    """
    if not text:
        return ""
    lowered = text.lower()
    return _WHITESPACE_RE.sub(" ", lowered).strip()


def embed(text: str) -> list[float]:
    """Tek bir metni 384 boyutlu, birim normlu (normalize) vektöre çevir."""
    model = _get_model()
    vector = model.encode(
        normalize_text(text),
        normalize_embeddings=True,
    )
    return vector.astype("float32").tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Birden çok metni toplu (batch) olarak vektörle — tek tek çağırmaktan hızlı."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(
        [normalize_text(t) for t in texts],
        normalize_embeddings=True,
        batch_size=32,
    )
    return [v.astype("float32").tolist() for v in vectors]
