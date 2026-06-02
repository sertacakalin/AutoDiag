"""Faz İ5 — GraphRAG değerlendirmesi.

DTC-seviyesinde teşhis doğruluğunu üç strateji için karşılaştırır:
  - Retrieval:  vaka retrieval'ından (hibrit+QN+rerank) DTC sıralaması
  - Graf:       bilgi grafiği teşhisinden (semptom→DTC) DTC sıralaması
  - GraphRAG:   ikisinin Reciprocal Rank Fusion ile birleşimi

Metrikler: Hit@1, Hit@3, MRR (ilk doğru DTC'nin sırasının tersi).
Alaka: sorgunun gold DTC kodları (hard_queries doğrudan; gold_set metinden eşlenir).

Çalıştırma:  cd eval && python run_graphrag_eval.py
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

from app.services.graph import FaultGraph  # noqa: E402
from app.services.graph_rag import (  # noqa: E402
    fuse_dtc_rankings, graph_dtc_codes, retrieval_dtc_codes,
)
from app.services.memory_store import MemoryEngine  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
DTC_CSV = os.path.join(ROOT_DIR, "data", "dtc_reference.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_graphrag.png")


def gold_codes(item, desc_to_code):
    if "dtc_codes" in item:
        return {c for c in item["dtc_codes"] if c}
    return {desc_to_code[d] for d in item.get("relevant_descriptions", [])
            if desc_to_code.get(d)}


def metrics(ranking, gold):
    """Hit@1, Hit@3, MRR (DTC sıralaması, gold kod kümesine karşı)."""
    hit1 = 1.0 if ranking[:1] and ranking[0] in gold else 0.0
    hit3 = 1.0 if any(c in gold for c in ranking[:3]) else 0.0
    rr = 0.0
    for i, c in enumerate(ranking, 1):
        if c in gold:
            rr = 1.0 / i
            break
    return hit1, hit3, rr


# Retrieval güven eşiği: üst sonucun benzerliği bunun üstündeyse retrieval'a
# güvenilir; altındaysa graf desteğiyle füzyon yapılır (adaptif GraphRAG).
CONF_TAU = 0.85


def evaluate(engine, fg, queries, desc_to_code):
    agg = {"Retrieval": [], "Graf": [], "GraphRAG": []}
    for item in queries:
        gold = gold_codes(item, desc_to_code)
        if not gold:
            continue
        q = item["query"]
        hits = engine.search(q, top_k=10, rerank=True, expand=True)
        rcodes = retrieval_dtc_codes(hits)
        gcodes = graph_dtc_codes(fg.diagnose(q, top_k=10))
        # Adaptif füzyon: retrieval eminse ona güven, değilse graf desteği.
        top_sim = hits[0].similarity if hits else 0.0
        fcodes = rcodes if top_sim >= CONF_TAU else fuse_dtc_rankings(rcodes, gcodes)
        agg["Retrieval"].append(metrics(rcodes, gold))
        agg["Graf"].append(metrics(gcodes, gold))
        agg["GraphRAG"].append(metrics(fcodes, gold))
    out = {}
    for name, rows in agg.items():
        arr = np.array(rows) if rows else np.zeros((1, 3))
        out[name] = {"Hit@1": float(arr[:, 0].mean()),
                     "Hit@3": float(arr[:, 1].mean()),
                     "MRR": float(arr[:, 2].mean())}
    return out


def main():
    df = pd.read_csv(CORPUS_CSV)
    desc_to_code = {}
    for d, c in zip(df["description"], df["dtc_code"].fillna("")):
        desc_to_code.setdefault(d, c if isinstance(c, str) and c else None)

    print(f"Motor + graf yükleniyor...")
    engine = MemoryEngine.from_csv(CORPUS_CSV)
    fg = FaultGraph.from_dtc_reference(DTC_CSV)

    with open(GOLD_PATH, encoding="utf-8") as f:
        gold = json.load(f)["queries"]
    with open(HARD_PATH, encoding="utf-8") as f:
        hard = json.load(f)["queries"]

    sets = {"Standart": evaluate(engine, fg, gold, desc_to_code),
            "Zorlu": evaluate(engine, fg, hard, desc_to_code)}

    for setname, res in sets.items():
        print(f"\n=== {setname} sorgular (DTC teşhis doğruluğu) ===")
        print(f"{'Strateji':<12}{'Hit@1':>9}{'Hit@3':>9}{'MRR':>9}")
        print("-" * 39)
        for name, sc in res.items():
            print(f"{name:<12}{sc['Hit@1']:>9.3f}{sc['Hit@3']:>9.3f}{sc['MRR']:>9.3f}")

    # GraphRAG kazancı (zorlu sette, retrieval'a göre).
    z = sets["Zorlu"]
    d = z["GraphRAG"]["MRR"] - z["Retrieval"]["MRR"]
    print(f"\nGraphRAG kazancı (zorlu, MRR): retrieval {z['Retrieval']['MRR']:.3f} "
          f"→ GraphRAG {z['GraphRAG']['MRR']:.3f} ({'+' if d>=0 else ''}{d:.3f})")
    _plot(sets)
    print(f"Grafik: {OUT_PNG}")


def _plot(sets):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    strategies = ["Retrieval", "Graf", "GraphRAG"]
    metrics_ = ["Hit@1", "Hit@3", "MRR"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, setname in zip(axes, ("Standart", "Zorlu")):
        x = np.arange(len(metrics_))
        w = 0.26
        for i, s in enumerate(strategies):
            vals = [sets[setname][s][m] for m in metrics_]
            b = ax.bar(x + (i - 1) * w, vals, w, label=s)
            ax.bar_label(b, fmt="%.2f", fontsize=7, padding=2)
        ax.set_title(f"{setname} sorgular", fontsize=11)
        ax.set_xticks(x); ax.set_xticklabels(metrics_)
        ax.set_ylim(0, 1.08); ax.set_ylabel("Skor")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(fontsize=9)
    fig.suptitle("AutoDiag — GraphRAG: Retrieval vs Graf vs Füzyon (Faz İ5)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
