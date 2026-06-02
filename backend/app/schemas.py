"""API istek/yanıt şemaları (Pydantic v2)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["düşük", "orta", "yüksek"]


class SearchRequest(BaseModel):
    """Arama isteği."""

    query: str = Field(min_length=3, description="Arıza açıklaması (serbest metin).")
    category: str | None = Field(default=None, description="Kategori filtresi (opsiyonel).")
    dtc_code: str | None = Field(default=None, description="DTC kodu filtresi (örn. P0300).")
    top_k: int = Field(default=5, ge=1, le=20, description="Dönecek sonuç sayısı.")
    use_rag: bool = Field(default=True, description="Teşhis önerisi üretilsin mi.")
    rerank: bool = Field(
        default=True,
        description="İki aşamalı arama: cross-encoder ile yeniden sıralama.",
    )
    expand_query: bool = Field(
        default=True,
        description="Sorgu genişletme: argo/günlük dili kanonik terimlerle zenginleştir.",
    )


class SearchHit(BaseModel):
    """Tek bir arama sonucu (geçmiş vaka)."""

    fault_id: str
    similarity: float = Field(description="0-1 arası benzerlik/alaka skoru.")
    description: str
    solution: str
    category: str
    dtc_code: str | None = None
    vehicle_model: str | None = None
    mileage_km: int | None = None
    rerank_score: float | None = Field(
        default=None, description="Cross-encoder rerank güveni (rerank açıksa)."
    )


class RagSuggestion(BaseModel):
    """Sentezlenmiş teşhis önerisi."""

    likely_cause: str
    recommended_steps: list[str] = Field(default_factory=list)
    confidence: Confidence = "düşük"


class SearchResponse(BaseModel):
    """Arama yanıtı: sonuçlar + (varsa) öneri + meta."""

    results: list[SearchHit]
    rag_suggestion: RagSuggestion | None = None
    query: str
    expanded_query: str | None = Field(
        default=None, description="Genişletme uygulandıysa efektif sorgu, yoksa null."
    )
    mode: str = Field(description="Aktif arama modu: 'hybrid' veya 'sparse'.")
    reranked: bool = Field(
        default=False, description="Sonuçlar cross-encoder ile yeniden sıralandı mı."
    )


class FaultCreate(BaseModel):
    """Yeni arıza kaydı girişi."""

    description: str = Field(min_length=3)
    category: str = Field(min_length=1)
    solution: str = Field(min_length=3)
    dtc_code: str | None = None
    vehicle_model: str | None = None
    mileage_km: int | None = Field(default=None, ge=0)


class FaultRead(BaseModel):
    """Tek bir arıza kaydının okunabilir gösterimi."""

    fault_id: str
    description: str
    category: str
    solution: str
    dtc_code: str | None = None
    vehicle_model: str | None = None
    mileage_km: int | None = None


class FeedbackCreate(BaseModel):
    """Bir sonucun faydalı olup olmadığına dair geri bildirim."""

    query_text: str = Field(min_length=1)
    returned_fault_id: str
    was_helpful: bool


class FeedbackAck(BaseModel):
    """Geri bildirim alındı onayı."""

    ok: bool = True
    total: int = Field(description="Toplam geri bildirim sayısı.")


class HealthResponse(BaseModel):
    """Servis sağlık durumu."""

    status: Literal["ok"] = "ok"
    mode: str
    fault_count: int
    categories: list[str]
    rag: Literal["llm", "extractive"]
    rerank_available: bool = False
