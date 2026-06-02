"""GraphRAG teşhis ucu (Faz İ5): retrieval + bilgi grafiği füzyonu.

Vaka retrieval'ı ile graf akıl yürütmesini (semptom→DTC→neden) birleştirir;
yapısal, neden-temelli bir teşhis döndürür.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_engine
from app.schemas import DiagnoseRequest, DiagnoseResponse, GraphDiagnosis
from app.services.graph_rag import graph_rag_diagnose
from app.services.memory_store import MemoryEngine
from app.services.query_norm import expand_query

router = APIRouter(prefix="/api", tags=["diagnose"])


@router.post("/diagnose", response_model=DiagnoseResponse)
def diagnose(
    req: DiagnoseRequest,
    request: Request,
    engine: MemoryEngine = Depends(get_engine),
) -> DiagnoseResponse:
    """Retrieval + graf füzyonuyla yapısal teşhis üret."""
    fault_graph = request.app.state.graph
    result = graph_rag_diagnose(req.query, engine, fault_graph, top_k=req.top_k)

    diagnoses = []
    for code in result.fused_codes:
        detail = fault_graph.dtc_detail(code)
        diagnoses.append(GraphDiagnosis(
            dtc_code=code,
            title=detail.get("title", ""),
            category=detail.get("category", ""),
            severity=detail.get("severity", ""),
            causes=detail.get("causes", []),
        ))

    expanded = expand_query(req.query)
    return DiagnoseResponse(
        query=req.query,
        expanded_query=expanded if expanded != req.query else None,
        diagnoses=diagnoses,
    )
