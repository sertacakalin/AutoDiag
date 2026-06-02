"""Domain-adaptation değerlendirmesi: base vs uyarlanmış embedding.

Aynı korpus ve held-out sorgu setleri (gold_set, hard_queries) üzerinde
base çok dilli MiniLM ile fine-tune edilmiş modeli karşılaştırır. Test
sorguları eğitimde KULLANILMADI.

Karşılaştırılan kurulumlar (her biri base vs adapted):
  - Dense        — yalnız embedding
  - Hibrit       — dense + BM25
  - Hibrit+QN    — dense + BM25 + sorgu genişletme

Metrikler: MRR, nDCG@5. Çıktı: konsol + eval/results_finetune.png

Çalıştırma:  cd eval && python run_finetune_eval.py
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

import run_ablation as ab  # metrikler + build_relevance (model bağımsız)  # noqa: E402
from app.services.embedding import normalize_text  # noqa: E402
from app.services.query_norm import expand_query  # noqa: E402

CORPUS_CSV = os.path.join(ROOT_DIR, "data", "faults_dataset.csv")
GOLD_PATH = os.path.join(EVAL_DIR, "gold_set.json")
HARD_PATH = os.path.join(EVAL_DIR, "hard_queries.json")
OUT_PNG = os.path.join(EVAL_DIR, "results_finetune.png")
BASE_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
ADAPTED_DIR = os.path.join(ROOT_DIR, "models", "autodiag-embed-tr")
DENSE_W, SPARSE_W = 0.7, 0.3


class ModelIndex:
    """Bir embedding modeli için dense matris + paylaşılan BM25."""

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
        q = self._encode([query])[0]
        return self.doc_vecs @ q

    def sparse(self, query):
        return np.array(self.bm25.get_scores(normalize_text(query).split()))


def rank_dense(idx, query):
    return list(np.argsort(-idx.dense(query)))


def rank_hybrid(idx, query):
    final = DENSE_W * ab._minmax(idx.dense(query)) + SPARSE_W * ab._minmax(idx.sparse(query))
    return list(np.argsort(-final))


def rank_hybrid_qn(idx, query):
    return rank_hybrid(idx, expand_query(query))


SETUPS = {"Dense": rank_dense, "Hibrit": rank_hybrid, "Hibrit+QN": rank_hybrid_qn}


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
    if not os.path.isdir(ADAPTED_DIR):
        print(f"HATA: uyarlanmış model yok: {ADAPTED_DIR}")
        print("Önce: python scripts/finetune_embedding.py")
        return

    from sentence_transformers import SentenceTransformer

    df = pd.read_csv(CORPUS_CSV)
    descriptions = df["description"].tolist()
    bm25 = BM25Okapi([normalize_text(d).split() for d in descriptions])
    std_q = load_queries(df, GOLD_PATH)
    hard_q = load_queries(df, HARD_PATH)
    print(f"Korpus: {len(descriptions)} | standart sorgu: {len(std_q)} | zorlu: {len(hard_q)}")

    print("\nBase model indeksleniyor...")
    base = ModelIndex(SentenceTransformer(BASE_MODEL), descriptions, bm25)
    print("Uyarlanmış model indeksleniyor...")
    adapted = ModelIndex(SentenceTransformer(ADAPTED_DIR), descriptions, bm25)

    def block(name, queries):
        print(f"\n=== {name} (nDCG@5 | MRR) ===")
        print(f"{'Kurulum':<14}{'Base':>18}{'Uyarlanmış':>18}{'Δ nDCG':>10}")
        print("-" * 60)
        rows = {}
        for setup, fn in SETUPS.items():
            b = evaluate(fn, base, queries)
            a = evaluate(fn, adapted, queries)
            d = a["nDCG@5"] - b["nDCG@5"]
            print(f"{setup:<14}"
                  f"{b['nDCG@5']:>9.3f} {b['MRR']:>7.3f}"
                  f"{a['nDCG@5']:>9.3f} {a['MRR']:>7.3f}"
                  f"{'+' if d>=0 else ''}{d:>8.3f}")
            rows[setup] = (b["nDCG@5"], a["nDCG@5"])
        return rows

    std_rows = block("Standart sorgular", std_q)
    hard_rows = block("Zorlu sorgular (argo)", hard_q)

    _plot(std_rows, hard_rows)
    print(f"\nGrafik: {OUT_PNG}")


def _plot(std_rows, hard_rows):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    setups = list(std_rows.keys())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, rows, title in [
        (axes[0], std_rows, "Standart sorgular"),
        (axes[1], hard_rows, "Zorlu sorgular (argo)"),
    ]:
        x = np.arange(len(setups))
        w = 0.36
        b = [rows[s][0] for s in setups]
        a = [rows[s][1] for s in setups]
        r1 = ax.bar(x - w / 2, b, w, label="Base")
        r2 = ax.bar(x + w / 2, a, w, label="Uyarlanmış")
        ax.bar_label(r1, fmt="%.2f", fontsize=7, padding=2)
        ax.bar_label(r2, fmt="%.2f", fontsize=7, padding=2)
        ax.set_title(title, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(setups, fontsize=9)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("nDCG@5")
        ax.grid(axis="y", alpha=0.3)
    axes[0].legend(loc="upper right", fontsize=9)
    fig.suptitle("AutoDiag — Embedding Domain-Adaptation (base vs uyarlanmış)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT_PNG, dpi=120, bbox_inches="tight")


if __name__ == "__main__":
    main()
