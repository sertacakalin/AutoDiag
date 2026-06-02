"""Faz İ6 — Diyaloglu / aktif teşhis (graf-güdümlü, LLM'siz).

Belirsiz bir arıza tarifinde sistem, adayları en iyi AYIRAN bir semptomu bilgi
grafiğinden (Faz İ4) seçip kullanıcıya sorar ("Şu belirti de var mı?"). Yanıt,
sorguyu zenginleştirir ve teşhisi daraltır. Bu "aktif bilgi arama", arama
kutusunu bir teşhis asistanına çevirir.

Protokol DURUMSUZDUR: istemci her turda biriken confirmed/denied semptomları
taşır; sunucu ya bir SORU ya da NİHAİ teşhis döndürür.

Tasarım: deterministik (kural + graf), açıklanabilir — teşhis aracında şart.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.embedding import normalize_text
from app.services.graph_rag import graph_rag_diagnose

MAX_TURNS = 3     # en fazla soru sayısı
N_CANDIDATES = 4  # ayrım için bakılacak aday DTC sayısı


@dataclass
class DialogueStep:
    """Bir diyalog adımı: ya soru ya nihai teşhis."""

    status: str                       # "question" | "final"
    question: str | None = None
    symptom: str | None = None        # sorulan ham semptom (yanıt için)
    diagnoses: list = field(default_factory=list)  # final ise dolu


def _effective_query(query: str, confirmed: list[str]) -> str:
    """Onaylanmış semptomları sorguya ekleyerek etkin sorguyu oluştur."""
    return f"{query} {' '.join(confirmed)}".strip() if confirmed else query


def _candidate_symptoms(graph, codes: list[str]) -> dict[str, list[str]]:
    """Aday DTC'lerin graf semptomlarını topla."""
    return {c: graph.dtc_detail(c).get("symptoms", []) for c in codes}


def rerank_by_consistency(
    graph, codes: list[str], confirmed: list[str], denied: list[str]
) -> list[str]:
    """Adayları, onaylanan/reddedilen belirtilerle GRAF tutarlılığına göre sırala.

    Onaylanan bir belirti bir DTC'nin graf semptomlarındaysa o DTC yükselir;
    reddedilen belirti varsa düşer. Stabil sıralama → tutarlılık eşitse füzyon
    sırası korunur. Diyalog yanıtlarını doğrudan teşhise yansıtır (yalnız sorgu
    metnine eklemekten çok daha güçlü).
    """
    conf = {normalize_text(s) for s in confirmed}
    den = {normalize_text(s) for s in denied}
    if not conf and not den:
        return codes

    def consistency(code: str) -> int:
        syms = {normalize_text(s) for s in graph.dtc_detail(code).get("symptoms", [])}
        return len(syms & conf) - len(syms & den)

    return sorted(codes, key=lambda c: -consistency(c))


def pick_discriminating_symptom(
    graph, candidate_codes: list[str], seen_texts: set[str]
) -> str | None:
    """Adayları en iyi ikiye bölen (bilgi kazancı yüksek) semptomu seç.

    seen_texts: sorguda/onaylı/reddedilmiş zaten geçen semptomlar (normalize).
    """
    cands = candidate_codes[:N_CANDIDATES]
    if len(cands) < 2:
        return None
    sym_by_code = _candidate_symptoms(graph, cands)

    # symptom_text -> kaç adayda görülüyor.
    counts: dict[str, int] = {}
    for syms in sym_by_code.values():
        for s in syms:
            if normalize_text(s) in seen_texts:
                continue
            counts[s] = counts.get(s, 0) + 1

    # Yalnız bazı adaylarda olan (ayırt edici) semptomlar; ideal split ≈ yarısı.
    half = len(cands) / 2
    discriminating = [(s, n) for s, n in counts.items() if 0 < n < len(cands)]
    if not discriminating:
        return None
    discriminating.sort(key=lambda x: (abs(x[1] - half), -x[1]))
    return discriminating[0][0]


def _categories_of(graph, codes: list[str]) -> list[str]:
    return [graph.dtc_detail(c).get("category", "") for c in codes]


def next_step(
    query: str,
    confirmed: list[str],
    denied: list[str],
    engine,
    graph,
    top_k: int = 5,
) -> DialogueStep:
    """Bir sonraki adımı belirle: netleştirici soru veya nihai teşhis."""
    eff = _effective_query(query, confirmed)
    result = graph_rag_diagnose(eff, engine, graph, top_k=max(top_k, N_CANDIDATES + 2))
    codes = result.fused_codes
    if not codes:
        return DialogueStep(status="final", diagnoses=[])

    # Diyalog yanıtlarını (onay/ret) graf tutarlılığıyla adaylara uygula.
    codes = rerank_by_consistency(graph, codes, confirmed, denied)

    # Belirsizlik sinyali: üst adaylar birden çok KATEGORİYE yayılıyor mu?
    # (Hangi alt-sistem? sorusu — netleştirici soru tam bunu çözer.)
    cats = [c for c in _categories_of(graph, codes[:3]) if c]
    confident = len(set(cats)) <= 1

    turns_used = len(confirmed) + len(denied)
    if confident or turns_used >= MAX_TURNS:
        return DialogueStep(status="final", diagnoses=_finalize(graph, codes[:top_k]))

    # Belirsiz → ayırt edici semptom sor.
    seen = {normalize_text(s) for s in confirmed + denied}
    seen |= set(normalize_text(query).split())  # kabaca sorgudaki kelimeler
    symptom = pick_discriminating_symptom(graph, codes, seen)
    if symptom is None:
        return DialogueStep(status="final", diagnoses=_finalize(graph, codes[:top_k]))

    return DialogueStep(
        status="question",
        question=f"Şu belirti de var mı: “{symptom}”?",
        symptom=symptom,
    )


def _finalize(graph, codes: list[str]) -> list[dict]:
    """Nihai teşhis listesi (yapısal detayla)."""
    out = []
    for c in codes:
        d = graph.dtc_detail(c)
        out.append({
            "dtc_code": c,
            "title": d.get("title", ""),
            "category": d.get("category", ""),
            "severity": d.get("severity", ""),
            "causes": d.get("causes", []),
        })
    return out
