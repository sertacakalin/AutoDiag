"""Faz İ3 — RAG kalite değerlendirmesi (LLM'siz, RAGAS-esinli).

RAGAS metriklerini bir LLM yargıç olmadan, embedding-tabanlı proxy'lerle hesaplar
(donanımda çalışır, deterministik). Ölçülen RAG katmanı, AutoDiag'ın extractive
öneri üreticisidir (rag.py fallback) — öneri yalnız getirilen vakalardan türetilir.

Metrikler:
  - Faithfulness / Groundedness: önerinin iddiaları getirilen bağlamdan ne kadar
    destekli (iddia↔bağlam embedding benzerliği). Yüksek = halüsinasyon yok.
  - Faithfulness (kontrol): aynı iddialar yerine RASTGELE vakalardan kurulmuş
    sahte öneri → DÜŞÜK çıkmalı (metriğin ayırt ettiğini kanıtlar).
  - Answer Relevancy: sorgu ↔ öneri embedding benzerliği.
  - Context Precision@k: getirilen vakaların alaka sıralaması (AP@k, DTC-tabanlı).
  - Context Recall@k: alakalı vakaların ne kadarı getirildi.

Çalıştırma:  cd eval && python run_rag_eval.py
"""

from __future__ import annotations

import json
import os
import random
import sys

import numpy as np
import pandas as pd

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from app.services.embedding import embed_batch  # noqa: E402
from app.services.memory_store import MemoryEngine  # noqa: E402
from app.services.rag import generate_suggestion  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_rag.png")
TOP_K = 5


def _cos_matrix(claims: list[str], context: list[str]) -> np.ndarray:
    """Her (iddia, bağlam) çifti için kosinüs benzerliği (vektörler birim normlu)."""
    if not claims or not context:
        return np.zeros((len(claims), max(len(context), 1)))
    cv = np.array(embed_batch(claims))
    xv = np.array(embed_batch(context))
    return cv @ xv.T


def groundedness(claims: list[str], context: list[str]) -> float:
    """Her iddianın bağlamdaki en yakın desteğe ortalama benzerliği (0-1)."""
    if not claims or not context:
        return 0.0
    sims = _cos_matrix(claims, context)
    return float(np.mean(sims.max(axis=1)))


def answer_relevancy(query: str, answer: str) -> float:
    if not answer.strip():
        return 0.0
    q, a = embed_batch([query, answer])
    return float(np.dot(q, a))


def avg_precision_at_k(rel_flags: list[bool]) -> float:
    """AP@k: alakalı vakaların sıralama kalitesi (RAGAS context precision'a yakın)."""
    R = sum(rel_flags)
    if R == 0:
        return 0.0
    hit, score = 0, 0.0
    for i, rel in enumerate(rel_flags, 1):
        if rel:
            hit += 1
            score += hit / i
    return score / R


def relevant_codes_for(item: dict, desc_to_code: dict) -> set:
    """Gold formatına göre alakalı DTC kod kümesi."""
    if "dtc_codes" in item:
        return {c for c in item["dtc_codes"] if c}
    codes = set()
    for d in item.get("relevant_descriptions", []):
        c = desc_to_code.get(d)
        if c:
            codes.add(c)
    return codes


def evaluate_set(engine, queries, desc_to_code, rng) -> dict:
    faith, faith_ctrl, relev, cprec, crecall = [], [], [], [], []
    corpus_solutions = engine_solutions(engine)

    for item in queries:
        q = item["query"]
        hits = engine.search(q, top_k=TOP_K, rerank=True, expand=True)
        if not hits:
            continue
        sugg = generate_suggestion(q, hits)
        claims = [sugg.likely_cause] + list(sugg.recommended_steps)
        context = [h.fault.solution for h in hits]

        faith.append(groundedness(claims, context))
        # Kontrol: rastgele vakalardan sahte öneri → aynı bağlama karşı ölç.
        fake = rng.sample(corpus_solutions, min(3, len(corpus_solutions)))
        faith_ctrl.append(groundedness(fake, context))

        answer = sugg.likely_cause + " " + " ".join(sugg.recommended_steps)
        relev.append(answer_relevancy(q, answer))

        codes = relevant_codes_for(item, desc_to_code)
        if codes:
            rel_flags = [(h.fault.dtc_code in codes) for h in hits]
            cprec.append(avg_precision_at_k(rel_flags))
            # Recall: alakalı KODLARIN top-k'da kapsanma oranı (distinct, ≤ 1).
            covered = {h.fault.dtc_code for h in hits if h.fault.dtc_code in codes}
            crecall.append(len(covered) / len(codes))

    return {
        "Faithfulness": float(np.mean(faith)),
        "Faithfulness(kontrol)": float(np.mean(faith_ctrl)),
        "AnswerRelevancy": float(np.mean(relev)),
        "ContextPrecision@5": float(np.mean(cprec)) if cprec else 0.0,
        "ContextRecall@5": float(np.mean(crecall)) if crecall else 0.0,
    }


def engine_solutions(engine) -> list[str]:
    return [engine.get(fid).solution for fid in engine._order]


def main():
    df = pd.read_csv(CORPUS_CSV)
    desc_to_code = {}
    for d, c in zip(df["description"], df["dtc_code"].fillna("")):
        desc_to_code.setdefault(d, c if isinstance(c, str) and c else None)

    print(f"Motor yükleniyor ({len(df)} vaka)...")
    engine = MemoryEngine.from_csv(CORPUS_CSV)
    rng = random.Random(42)

    with open(GOLD_PATH, encoding="utf-8") as f:
        gold = json.load(f)["queries"]
    with open(HARD_PATH, encoding="utf-8") as f:
        hard = json.load(f)["queries"]

    print("Değerlendiriliyor (extractive RAG)...\n")
    sets = {
        "Standart": evaluate_set(engine, gold, desc_to_code, rng),
        "Zorlu": evaluate_set(engine, hard, desc_to_code, rng),
    }

    metrics = ["Faithfulness", "Faithfulness(kontrol)", "AnswerRelevancy",
               "ContextPrecision@5", "ContextRecall@5"]
    print(f"{'Metrik':<24}{'Standart':>12}{'Zorlu':>12}")
    print("-" * 48)
    for m in metrics:
        print(f"{m:<24}{sets['Standart'][m]:>12.3f}{sets['Zorlu'][m]:>12.3f}")

    gap = sets["Standart"]["Faithfulness"] - sets["Standart"]["Faithfulness(kontrol)"]
    print(f"\nFaithfulness ayrımı (gerçek − kontrol): {gap:+.3f} "
          f"→ metrik halüsinasyonu ayırt ediyor.")
    _plot(sets, metrics)
    print(f"Grafik: {OUT_PNG}")


def _plot(sets, metrics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.arange(len(metrics))
    w = 0.38
    fig, ax = plt.subplots(figsize=(11, 5))
    b1 = ax.bar(x - w/2, [sets["Standart"][m] for m in metrics], w, label="Standart")
    b2 = ax.bar(x + w/2, [sets["Zorlu"][m] for m in metrics], w, label="Zorlu")
    ax.bar_label(b1, fmt="%.2f", fontsize=7, padding=2)
    ax.bar_label(b2, fmt="%.2f", fontsize=7, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("(kontrol)", "\n(kontrol)") for m in metrics], fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Skor")
    ax.set_title("AutoDiag — RAG Kalite Değerlendirmesi (RAGAS-esinli, LLM'siz, Faz İ3)")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
