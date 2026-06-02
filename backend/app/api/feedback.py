"""Geri bildirim ucu: bir sonucun faydalı olup olmadığını kaydeder.

Demo modunda geri bildirimler bellekte tutulur; DB modunda Feedback tablosuna
yazılır. Geri bildirim, ileride re-ranking/öğrenme için sinyal kaynağıdır.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_engine, get_feedback_store
from app.schemas import FeedbackAck, FeedbackCreate
from app.services.memory_store import MemoryEngine

router = APIRouter(prefix="/api", tags=["feedback"])


@router.post("/feedback", response_model=FeedbackAck)
def submit_feedback(
    payload: FeedbackCreate,
    engine: MemoryEngine = Depends(get_engine),
    store: list = Depends(get_feedback_store),
) -> FeedbackAck:
    """Bir sonuç için faydalı/değil geri bildirimini kaydet."""
    if engine.get(payload.returned_fault_id) is None:
        raise HTTPException(status_code=404, detail="İlgili kayıt bulunamadı.")
    store.append(payload.model_dump())
    return FeedbackAck(ok=True, total=len(store))
