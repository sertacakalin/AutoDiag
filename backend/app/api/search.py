"""Arama ucu: hibrit arama + (istenirse) RAG teşhis önerisi."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_engine
from app.schemas import RagSuggestion, SearchHit, SearchRequest, SearchResponse
from app.services.memory_store import Hit, MemoryEngine
from app.services.rag import generate_suggestion

router = APIRouter(prefix="/api", tags=["search"])


def _to_hit_schema(hit: Hit) -> SearchHit:
    """Dahili Hit nesnesini API şemasına çevir."""
    f = hit.fault
    return SearchHit(
        fault_id=f.id,
        similarity=round(hit.similarity, 4),
        description=f.description,
        solution=f.solution,
        category=f.category,
        dtc_code=f.dtc_code,
        vehicle_model=f.vehicle_model,
        mileage_km=f.mileage_km,
        rerank_score=round(hit.rerank_score, 4) if hit.rerank_score is not None else None,
    )


@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, engine: MemoryEngine = Depends(get_engine)) -> SearchResponse:
    """Geçmiş vakalarda hibrit arama yap; isteğe bağlı teşhis önerisi üret."""
    hits = engine.search(
        query=req.query,
        top_k=req.top_k,
        category=req.category,
        dtc_code=req.dtc_code,
        rerank=req.rerank,
        expand=req.expand_query,
    )
    reranked = req.rerank and any(h.rerank_score is not None for h in hits)

    expanded: str | None = None
    if req.expand_query:
        from app.services.query_norm import expand_query

        effective = expand_query(req.query)
        if effective != req.query:
            expanded = effective

    suggestion: RagSuggestion | None = None
    if req.use_rag:
        raw = generate_suggestion(req.query, hits)
        suggestion = RagSuggestion(
            likely_cause=raw.likely_cause,
            recommended_steps=raw.recommended_steps,
            confidence=raw.confidence,  # type: ignore[arg-type]
        )

    return SearchResponse(
        results=[_to_hit_schema(h) for h in hits],
        rag_suggestion=suggestion,
        query=req.query,
        expanded_query=expanded,
        mode=engine.mode,
        reranked=reranked,
    )
