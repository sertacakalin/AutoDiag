"""Faz İ6 — Diyaloglu (aktif) teşhis değerlendirmesi.

Netleştirici soruların teşhis doğruluğuna katkısını ölçer. Oracle simülasyonu:
gerçekten gold arızaya sahip bir kullanıcı varsayılır; sistem bir semptom
sorduğunda, o semptom gold DTC'nin graf semptomları arasındaysa "EVET", değilse
"HAYIR" yanıtı verilir. Soru-yanıt döngüsünden ÖNCE ve SONRA Hit@1/Hit@3/MRR
karşılaştırılır.

Çalıştırma:  cd eval && python run_dialogue_eval.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

from app.services.dialogue import MAX_TURNS, next_step  # noqa: E402
from app.services.embedding import normalize_text  # noqa: E402
from app.services.graph import FaultGraph  # noqa: E402
from app.services.graph_rag import graph_rag_diagnose  # noqa: E402
from app.services.memory_store import MemoryEngine  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
DTC_CSV = os.path.join(ROOT_DIR, "data", "dtc_reference.csv")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_dialogue.png")


def gold_symptoms(graph, codes) -> set[str]:
    out = set()
    for c in codes:
        for s in graph.dtc_detail(c).get("symptoms", []):
            out.add(normalize_text(s))
    return out


def hit_metrics(codes, gold):
    h1 = 1.0 if codes[:1] and codes[0] in gold else 0.0
    h3 = 1.0 if any(c in gold for c in codes[:3]) else 0.0
    rr = next((1.0 / i for i, c in enumerate(codes, 1) if c in gold), 0.0)
    return h1, h3, rr


def simulate(engine, graph, query, gold):
    """Oracle ile diyalog döngüsünü işlet; nihai DTC sıralamasını döndür."""
    gsym = gold_symptoms(graph, gold)
    confirmed, denied, asked = [], [], 0
    step = next_step(query, confirmed, denied, engine, graph)
    while step.status == "question" and asked < MAX_TURNS:
        asked += 1
        if normalize_text(step.symptom) in gsym:
            confirmed.append(step.symptom)
        else:
            denied.append(step.symptom)
        step = next_step(query, confirmed, denied, engine, graph)
    final_codes = [d["dtc_code"] for d in step.diagnoses]
    return final_codes, asked


def main():
    df = pd.read_csv(CORPUS_CSV)
    print("Motor + graf yükleniyor...")
    engine = MemoryEngine.from_csv(CORPUS_CSV)
    graph = FaultGraph.from_dtc_reference(DTC_CSV)

    with open(HARD_PATH, encoding="utf-8") as f:
        queries = json.load(f)["queries"]

    before, after, asked_counts = [], [], []
    for item in queries:
        gold = {c for c in item.get("dtc_codes", []) if c}
        if not gold:
            continue
        q = item["query"]
        before_codes = graph_rag_diagnose(q, engine, graph, top_k=5).fused_codes
        before.append(hit_metrics(before_codes, gold))
        after_codes, asked = simulate(engine, graph, q, gold)
        after.append(hit_metrics(after_codes, gold))
        asked_counts.append(asked)

    b = np.array(before)
    a = np.array(after)
    labels = ["Hit@1", "Hit@3", "MRR"]
    print(f"\nZorlu sorgular (n={len(before)}), ort. soru sayısı: {np.mean(asked_counts):.1f}\n")
    print(f"{'Metrik':<10}{'Diyalogsuz':>12}{'Diyaloglu':>12}{'Δ':>9}")
    print("-" * 43)
    for i, m in enumerate(labels):
        bi, ai = b[:, i].mean(), a[:, i].mean()
        print(f"{m:<10}{bi:>12.3f}{ai:>12.3f}{ai-bi:>+9.3f}")

    _plot(labels, b.mean(axis=0), a.mean(axis=0))
    print(f"\nGrafik: {OUT_PNG}")


def _plot(labels, before, after):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = np.arange(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(8, 5))
    b1 = ax.bar(x - w/2, before, w, label="Diyalogsuz (tek atış)")
    b2 = ax.bar(x + w/2, after, w, label="Diyaloglu (aktif soru)")
    ax.bar_label(b1, fmt="%.2f", fontsize=8, padding=2)
    ax.bar_label(b2, fmt="%.2f", fontsize=8, padding=2)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylim(0, 1.05); ax.set_ylabel("Skor")
    ax.set_title("AutoDiag — Aktif Diyalog Teşhisin Katkısı (zorlu sorgular, Faz İ6)")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
