"""Faz İ1 — Embedding modeli karşılaştırması.

Çok dilli MiniLM (base ve domain-adapte) ile Türkçe-native modelleri aynı
held-out setlerde (gold_set, hard_queries) karşılaştırır. Amaç: Türkçe-özel bir
modelin, özellikle argo sorgularda, çok dilli modele üstünlüğünü ölçmek.

Kurulumlar: Dense (yalnız embedding) ve Hibrit+QN (dense+BM25+sorgu genişletme).
Metrikler: MRR, nDCG@5.

Çalıştırma:  cd eval && python run_model_compare.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(EVAL_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "backend"))

import run_ablation as ab  # noqa: E402
from app.services.embedding import normalize_text  # noqa: E402
from app.services.query_norm import expand_query  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_models.png")

# Karşılaştırılacak modeller: ad → model id / yerel yol.
MODELS = {
    "MiniLM-base": "paraphrase-multilingual-MiniLM-L12-v2",
    "TR-trmteb": "trmteb/turkish-embedding-model",
    "TR-trmteb-adapte": os.path.join(ROOT_DIR, "models", "autodiag-embed-tr-trmteb"),
    "TR-adapte-HN": os.path.join(ROOT_DIR, "models", "autodiag-embed-tr-hn"),
}
DENSE_W, SPARSE_W = 0.7, 0.3


class ModelIndex:
    def __init__(self, model, descriptions, bm25):
        self.model = model
        self.descriptions = descriptions
        self.bm25 = bm25
        self.doc_vecs = self._encode(descriptions)

    def _encode(self, texts):
        return np.array(
            self.model.encode(
                [normalize_text(t) for t in texts], normalize_embeddings=True
            )
        )

    def dense(self, query):
        return self.doc_vecs @ self._encode([query])[0]

    def sparse(self, query):
        return np.array(self.bm25.get_scores(normalize_text(query).split()))


def rank_dense(idx, query):
    return list(np.argsort(-idx.dense(query)))


def rank_hybrid_qn(idx, query):
    q = expand_query(query)
    final = DENSE_W * ab._minmax(idx.dense(q)) + SPARSE_W * ab._minmax(idx.sparse(q))
    return list(np.argsort(-final))


def evaluate(rank_fn, idx, queries):
    mrr, ndcg = [], []
    for item in queries:
        ranked = rank_fn(idx, item["query"])
        mrr.append(ab.reciprocal_rank(ranked, item["relevant"]))
        ndcg.append(ab.ndcg_at_k(ranked, item["relevant"], 5))
    return {"MRR": float(np.mean(mrr)), "nDCG@5": float(np.mean(ndcg))}


def load_queries(df, path):
    with open(path, encoding="utf-8") as f:
        return ab.build_relevance(df, json.load(f)["queries"])


def main():
    from sentence_transformers import SentenceTransformer

    df = pd.read_csv(CORPUS_CSV)
    descriptions = df["description"].tolist()
    bm25 = BM25Okapi([normalize_text(d).split() for d in descriptions])
    std_q = load_queries(df, GOLD_PATH)
    hard_q = load_queries(df, HARD_PATH)
    print(f"Korpus: {len(descriptions)} | standart: {len(std_q)} | zorlu: {len(hard_q)}\n")

    # results[model][set][setup] = (MRR, nDCG)
    results: dict = {}
    for name, ref in MODELS.items():
        # Yalnız YEREL (mutlak yol) model yoksa atla; HF id'leri (org/model) atlanmaz.
        if os.path.isabs(ref) and not os.path.isdir(ref):
            print(f"ATLA {name}: yerel model yok ({ref})")
            continue
        print(f"İndeksleniyor: {name} ...")
        idx = ModelIndex(SentenceTransformer(ref), descriptions, bm25)
        results[name] = {
            "Standart": {
                "Dense": evaluate(rank_dense, idx, std_q),
                "Hibrit+QN": evaluate(rank_hybrid_qn, idx, std_q),
            },
            "Zorlu": {
                "Dense": evaluate(rank_dense, idx, hard_q),
                "Hibrit+QN": evaluate(rank_hybrid_qn, idx, hard_q),
            },
        }

    for setname in ("Standart", "Zorlu"):
        print(f"\n=== {setname} sorgular (nDCG@5 | MRR) ===")
        print(f"{'Model':<18}{'Dense':>18}{'Hibrit+QN':>18}")
        print("-" * 54)
        for name, r in results.items():
            d, h = r[setname]["Dense"], r[setname]["Hibrit+QN"]
            print(f"{name:<18}{d['nDCG@5']:>9.3f} {d['MRR']:>7.3f}"
                  f"{h['nDCG@5']:>9.3f} {h['MRR']:>7.3f}")

    # En iyi (zorlu sette Hibrit+QN nDCG@5).
    best = max(results, key=lambda n: results[n]["Zorlu"]["Hibrit+QN"]["nDCG@5"])
    print(f"\nZorlu sette en iyi (Hibrit+QN nDCG@5): {best} "
          f"({results[best]['Zorlu']['Hibrit+QN']['nDCG@5']:.3f})")

    _plot(results)
    print(f"Grafik: {OUT_PNG}")


def _plot(results):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    models = list(results.keys())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, setname in zip(axes, ("Standart", "Zorlu")):
        x = np.arange(len(models))
        w = 0.36
        dense = [results[m][setname]["Dense"]["nDCG@5"] for m in models]
        hyb = [results[m][setname]["Hibrit+QN"]["nDCG@5"] for m in models]
        b1 = ax.bar(x - w / 2, dense, w, label="Dense")
        b2 = ax.bar(x + w / 2, hyb, w, label="Hibrit+QN")
        ax.bar_label(b1, fmt="%.2f", fontsize=7, padding=2)
        ax.bar_label(b2, fmt="%.2f", fontsize=7, padding=2)
        ax.set_title(f"{setname} sorgular", fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(models, fontsize=8, rotation=15)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("nDCG@5")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("AutoDiag — Embedding Modeli Karşılaştırması (Faz İ1)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
