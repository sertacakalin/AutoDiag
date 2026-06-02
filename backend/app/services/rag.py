"""RAG katmanı: en benzer vakalardan yapılandırılmış teşhis önerisi üretir.

LLM_API_KEY yoksa veya LLM çağrısı başarısız olursa, doğrudan vakalardan
çıkarımsal (extractive) bir fallback öneri döner. Asla vakaların dışına çıkılmaz.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

import httpx

from app.config import get_settings

# Anthropic Messages API ayarları (LLM_API_KEY verilince kullanılır).
LLM_MODEL = "claude-3-5-sonnet-20241022"
LLM_URL = "https://api.anthropic.com/v1/messages"
LLM_MAX_TOKENS = 700
LLM_TIMEOUT = 30.0


@dataclass
class RagSuggestion:
    """Sentezlenmiş teşhis önerisi."""

    likely_cause: str
    recommended_steps: list[str] = field(default_factory=list)
    confidence: str = "düşük"  # "düşük" | "orta" | "yüksek"

    def to_dict(self) -> dict:
        return asdict(self)


def _hit_field(hit, name: str, default=None):
    """hit hem dict hem nesne olabilir; ilgili alanı güvenle oku."""
    if isinstance(hit, dict):
        return hit.get(name, default)
    return getattr(hit, name, default)


def _fallback(hits: list) -> RagSuggestion:
    """LLM olmadan: en benzer kaydın çözümünü temel öneri olarak kullan."""
    if not hits:
        return RagSuggestion(
            likely_cause="Benzer geçmiş vaka bulunamadı.",
            recommended_steps=[],
            confidence="düşük",
        )

    likely_cause = _hit_field(hits[0], "solution") or "Belirsiz"
    steps = [
        s for s in (_hit_field(h, "solution") for h in hits[:3]) if s
    ]
    return RagSuggestion(
        likely_cause=likely_cause,
        recommended_steps=steps,
        confidence="orta",
    )


def _build_prompt(query: str, hits: list) -> str:
    """Vakaları '%benzerlik - açıklama → çözüm' satırlarına döküp prompt'a göm."""
    lines = []
    for h in hits:
        sim = _hit_field(h, "similarity", 0.0) or 0.0
        desc = _hit_field(h, "description", "")
        sol = _hit_field(h, "solution", "")
        lines.append(f"- %{round(float(sim) * 100)} benzer: {desc} → çözüm: {sol}")
    cases = "\n".join(lines) if lines else "(benzer vaka yok)"

    return (
        "Sen bir otomotiv arıza teşhis asistanısın. SADECE aşağıda verilen geçmiş "
        "vakalara dayanarak öneri ver; bilgi UYDURMA, vakaların dışına çıkma.\n\n"
        f"Kullanıcının arızası: {query}\n\n"
        f"Benzer geçmiş vakalar:\n{cases}\n\n"
        "Yanıtı SADECE şu JSON formatında ver, başka metin yazma:\n"
        '{"likely_cause": "<en olası neden>", '
        '"recommended_steps": ["<adım1>", "<adım2>", "..."], '
        '"confidence": "<düşük|orta|yüksek>"}'
    )


def _extract_json(text: str) -> dict:
    """LLM yanıtındaki ilk JSON nesnesini ayıkla ve ayrıştır."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("Yanıtta JSON bulunamadı")
    return json.loads(match.group(0))


def _call_llm(prompt: str, api_key: str) -> RagSuggestion:
    """Anthropic Messages API'sini çağır ve JSON yanıtı RagSuggestion'a çevir."""
    resp = httpx.post(
        LLM_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "max_tokens": LLM_MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=LLM_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"]
    data = _extract_json(text)
    return RagSuggestion(
        likely_cause=str(data.get("likely_cause", "")).strip() or "Belirsiz",
        recommended_steps=[str(s) for s in data.get("recommended_steps", [])],
        confidence=str(data.get("confidence", "orta")).strip() or "orta",
    )


def generate_suggestion(query: str, hits: list) -> RagSuggestion:
    """Teşhis önerisi üret. LLM anahtarı varsa LLM, yoksa/başarısızsa fallback."""
    api_key = get_settings().LLM_API_KEY
    if not api_key:
        return _fallback(hits)

    try:
        return _call_llm(_build_prompt(query, hits), api_key)
    except Exception as exc:  # ağ/parse/anahtar hatası → güvenli fallback
        print(f"[rag] LLM çağrısı başarısız, fallback'e düşülüyor: {exc}")
        return _fallback(hits)
