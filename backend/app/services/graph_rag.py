"""Faz İ5 — GraphRAG: retrieval + bilgi grafiğini birleştir.

Vanilla RAG yalnız metin-benzerliğiyle getirilen vakalara dayanır. GraphRAG,
buna bilgi grafiğinin yapısal akıl yürütmesini (semptom → DTC → neden) ekler ve
iki sinyali Reciprocal Rank Fusion (RRF) ile birleştirir. Böylece teşhis,
neden-sonuç yollarına da dayandırılır (halüsinasyon ↓, kapsama ↑).
"""

from __future__ import annotations

from dataclasses import dataclass, field

RRF_K = 60  # RRF sabiti (standart)


def _rank_map(codes: list[str]) -> dict[str, int]:
    """Sıralı (tekrarsız) kod listesini {kod: sıra} haritasına çevir."""
    seen: dict[str, int] = {}
    for code in codes:
        if code and code not in seen:
            seen[code] = len(seen)
    return seen


def fuse_dtc_rankings(
    retrieval_codes: list[str],
    graph_codes: list[str],
    retrieval_weight: float = 1.0,
    graph_weight: float = 0.35,
) -> list[str]:
    """İki DTC sıralamasını ağırlıklı Reciprocal Rank Fusion ile birleştir.

    Retrieval güçlü temel sinyaldir; graf (seyrek, yapısal) DESTEKLEYİCİ olarak
    daha düşük ağırlık alır. Böylece graf, güçlü retrieval'ı bozmadan uyuşan
    kodları yukarı taşır ve retrieval boş kaldığında yedek görevi görür.
    """
    r = _rank_map(retrieval_codes)
    g = _rank_map(graph_codes)
    scores: dict[str, float] = {}
    for code in set(r) | set(g):
        s = 0.0
        if code in r:
            s += retrieval_weight / (RRF_K + r[code])
        if code in g:
            s += graph_weight / (RRF_K + g[code])
        scores[code] = s
    return [c for c, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def retrieval_dtc_codes(hits) -> list[str]:
    """Retrieval sonuçlarından sıralı (tekrarsız) DTC kodları."""
    out: list[str] = []
    for h in hits:
        code = h.fault.dtc_code
        if code and code not in out:
            out.append(code)
    return out


def graph_dtc_codes(diagnoses) -> list[str]:
    """Graf teşhislerinden sıralı DTC kodları."""
    out: list[str] = []
    for d in diagnoses:
        if d.dtc_code and d.dtc_code not in out:
            out.append(d.dtc_code)
    return out


@dataclass
class GraphRagResult:
    """GraphRAG füzyon teşhisi."""

    fused_codes: list[str]
    top_causes: list[str] = field(default_factory=list)
    top_category: str = ""
    severity: str = ""


def graph_rag_diagnose(query, engine, fault_graph, top_k: int = 5) -> GraphRagResult:
    """Retrieval + graf teşhisini RRF ile birleştir; yapısal bağlam döndür."""
    hits = engine.search(query, top_k=top_k, rerank=True, expand=True)
    diagnoses = fault_graph.diagnose(query, top_k=top_k)

    fused = fuse_dtc_rankings(retrieval_dtc_codes(hits), graph_dtc_codes(diagnoses))

    # En iyi füzyon kodunun graf yapısal bağlamını (neden/kategori) çek.
    top_causes, category, severity = [], "", ""
    if fused:
        sub = fault_graph.subgraph_for_dtc(fused[0])
        top_causes = sub.get("causes", [])
        category = sub.get("category", "")
    if diagnoses:
        severity = diagnoses[0].severity
    return GraphRagResult(
        fused_codes=fused[:top_k], top_causes=top_causes,
        top_category=category, severity=severity,
    )
