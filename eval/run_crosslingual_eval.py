"""Faz İ2 — Çapraz-dilli değerlendirme (gerçek Zenodo verisi).

Türkçe sorgularla, İngilizce gerçek arıza vakalarını (Zenodo, CC-BY) retrieval.
Alaka ölçütü: aynı Zenodo source_category. İki şeyi gösterir:
  1. Sistem GERÇEK, bağımsız kaynaklı veride çalışır (sentetik değil).
  2. Çapraz-dilli retrieval: çok dilli model (MiniLM) TR↔EN hizalamada güçlü;
     Türkçe-native model tek-dilli Türkçede güçlü ama çapraz-dilde sınırlı.
     BM25 (lexical) çapraz-dilde tamamen çöker (kelime örtüşmesi yok).

Çalıştırma:  cd eval && python run_crosslingual_eval.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

import run_ablation as ab  # noqa: E402
from app.services.embedding import normalize_text  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "real", "zenodo_faults.csv")
QUERIES = os.path.join(EVAL_DIR, "crosslingual_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_crosslingual.png")

MODELS = {
    "MiniLM-base (çok dilli)": "paraphrase-multilingual-MiniLM-L12-v2",
    "TR-trmteb-adapte": os.path.join(ROOT_DIR, "models", "autodiag-embed-tr-trmteb"),
}


def build_relevance(df, queries):
    cats = df["source_category"].tolist()
    out = []
    for item in queries:
        target = item["category"]
        relevant = {i for i, c in enumerate(cats) if c == target}
        out.append({"query": item["query"], "relevant": relevant})
    return out


class Idx:
    def __init__(self, model, descs, bm25):
        self.model, self.descs, self.bm25 = model, descs, bm25
        self.docv = np.array(model.encode([normalize_text(d) for d in descs],
                                          normalize_embeddings=True))

    def dense(self, q):
        return self.docv @ np.array(self.model.encode([normalize_text(q)],
                                                       normalize_embeddings=True)[0])

    def sparse(self, q):
        return np.array(self.bm25.get_scores(normalize_text(q).split()))


def evaluate(rank_fn, idx, queries):
    p3, mrr, ndcg = [], [], []
    for it in queries:
        r = rank_fn(idx, it["query"])
        p3.append(ab.precision_at_k(r, it["relevant"], 3))
        mrr.append(ab.reciprocal_rank(r, it["relevant"]))
        ndcg.append(ab.ndcg_at_k(r, it["relevant"], 5))
    return {"P@3": float(np.mean(p3)), "MRR": float(np.mean(mrr)),
            "nDCG@5": float(np.mean(ndcg))}


def main():
    from sentence_transformers import SentenceTransformer

    df = pd.read_csv(CORPUS_CSV)
    descs = df["description"].tolist()
    bm25 = BM25Okapi([normalize_text(d).split() for d in descs])
    with open(QUERIES, encoding="utf-8") as f:
        queries = build_relevance(df, json.load(f)["queries"])

    print(f"Gerçek korpus (Zenodo, CC-BY): {len(descs)} vaka")
    dist = Counter(df["source_category"])
    print(f"Sorgu: {len(queries)} (TR) | hedef kategoriler gerçek veride mevcut\n")

    # Lexical (BM25) çapraz-dilde — referans (çökmesi beklenir).
    bm25_only = Idx.__new__(Idx)
    bm25_only.bm25 = bm25
    bm25_scores = evaluate(lambda i, q: list(np.argsort(-i.sparse(q))),
                           bm25_only, queries)
    print(f"{'Yöntem/Model':<28}{'P@3':>9}{'MRR':>9}{'nDCG@5':>9}")
    print("-" * 55)
    print(f"{'BM25 (lexical)':<28}{bm25_scores['P@3']:>9.3f}"
          f"{bm25_scores['MRR']:>9.3f}{bm25_scores['nDCG@5']:>9.3f}")

    results = {"BM25 (lexical)": bm25_scores}
    for name, ref in MODELS.items():
        if os.path.isabs(ref) and not os.path.isdir(ref):
            print(f"ATLA {name}: yerel model yok")
            continue
        idx = Idx(SentenceTransformer(ref), descs, bm25)
        sc = evaluate(lambda i, q: list(np.argsort(-i.dense(q))), idx, queries)
        results[f"Dense: {name}"] = sc
        print(f"{'Dense: '+name:<28}{sc['P@3']:>9.3f}{sc['MRR']:>9.3f}{sc['nDCG@5']:>9.3f}")

    print("\nYorum: BM25 çapraz-dilde çöker (TR↔EN kelime örtüşmesi yok); "
          "çok dilli embedding semantik köprü kurar.")
    _plot(results)
    print(f"Grafik: {OUT_PNG}")


def _plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = list(results.keys())
    metrics = ["P@3", "MRR", "nDCG@5"]
    x = np.arange(len(metrics))
    w = 0.8 / len(names)
    fig, ax = plt.subplots(figsize=(9, 5))
    for i, n in enumerate(names):
        vals = [results[n][m] for m in metrics]
        b = ax.bar(x + (i - (len(names)-1)/2) * w, vals, w, label=n)
        ax.bar_label(b, fmt="%.2f", fontsize=7, padding=2)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Skor")
    ax.set_title("AutoDiag — Çapraz-dilli retrieval (TR sorgu → EN gerçek vaka, Faz İ2)")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
