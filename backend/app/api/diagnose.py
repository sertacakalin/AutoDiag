"""GraphRAG teşhis ucu (Faz İ5): retrieval + bilgi grafiği füzyonu.

Vaka retrieval'ı ile graf akıl yürütmesini (semptom→DTC→neden) birleştirir;
yapısal, neden-temelli bir teşhis döndürür.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_engine
from app.schemas import (
    DiagnoseRequest,
    DiagnoseResponse,
    GraphDiagnosis,
    InteractiveDiagnoseRequest,
    InteractiveDiagnoseResponse,
)
from app.services.dialogue import next_step
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
    from app.observability import DIAGNOSES

    DIAGNOSES.inc()
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


@router.post("/diagnose/interactive", response_model=InteractiveDiagnoseResponse)
def diagnose_interactive(
    req: InteractiveDiagnoseRequest,
    request: Request,
    engine: MemoryEngine = Depends(get_engine),
) -> InteractiveDiagnoseResponse:
    """Diyaloglu teşhis: belirsizlikte netleştirici soru sor, değilse sonuçla."""
    fault_graph = request.app.state.graph
    step = next_step(req.query, req.confirmed, req.denied, engine, fault_graph, req.top_k)
    return InteractiveDiagnoseResponse(
        status=step.status,  # type: ignore[arg-type]
        question=step.question,
        symptom=step.symptom,
        diagnoses=[GraphDiagnosis(**d) for d in step.diagnoses],
    )

